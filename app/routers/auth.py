from uuid import UUID
import logging
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth import PerfilPermissao, Usuario
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    MeResponse,
    RefreshRequest,
)
from app.security.dependencies import get_current_context
from app.security.jwt import create_preauth_token, decode_token
from app.security.mfa import (
    decrypt_secret,
    encrypt_secret,
    generate_secret,
    provisioning_uri,
    verify_totp,
)
from app.security.password import verify_password
from app.services.auth_service import (
    create_session,
    refresh_token_fingerprint,
    resolve_empresa,
    revoke_session,
    rotate_refresh_session,
    utcnow,
)

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])
logger = logging.getLogger("mdp.auth")


def _usuario_por_preauth(db: Session, token: str, purpose: str):
    try:
        payload = decode_token(token, "preauth")
        if payload.get("purpose") != purpose:
            raise jwt.InvalidTokenError("Finalidade inválida")
        usuario = db.query(Usuario).filter(
            Usuario.id == UUID(payload["sub"]),
            Usuario.ativo.is_(True),
        ).first()
        if not usuario:
            raise jwt.InvalidTokenError("Usuário inválido")
        empresa_id = UUID(payload["empresa_id"]) if payload.get("empresa_id") else None
        return usuario, empresa_id
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Token de pré-autenticação inválido ou expirado.",
        )


@router.post("/login", response_model=LoginResponse)
def login(dados: LoginRequest, request: Request, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(
        Usuario.email == dados.email.lower().strip()
    ).first()
    now = utcnow()

    if not usuario or not usuario.ativo:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    if usuario.bloqueado_ate and usuario.bloqueado_ate > now:
        raise HTTPException(status_code=423, detail="Login temporariamente bloqueado.")

    if not verify_password(dados.senha, usuario.password_hash):
        usuario.tentativas_login += 1
        if usuario.tentativas_login >= settings.max_login_attempts:
            usuario.bloqueado_ate = now + settings.login_lockout_delta
            usuario.tentativas_login = 0
        db.commit()
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    usuario.tentativas_login = 0
    usuario.bloqueado_ate = None

    empresa_id, vinculo = resolve_empresa(db, usuario, dados.empresa_id)

    if vinculo == "MULTIPLAS_EMPRESAS":
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Informe empresa_id para selecionar a empresa ativa.",
        )

    # Inclusive para superadmin: empresa informada precisa existir e estar ativa.
    if dados.empresa_id and empresa_id is None:
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Empresa inexistente, inativa ou sem acesso autorizado.",
        )

    mfa_obrigatorio = usuario.is_superadmin or usuario.mfa_habilitado
    if mfa_obrigatorio:
        purpose = (
            "mfa_verify"
            if usuario.mfa_habilitado and usuario.mfa_secret_enc
            else "mfa_setup"
        )
        token = create_preauth_token(usuario.id, empresa_id, purpose)
        db.commit()
        return LoginResponse(status=purpose.upper(), preauth_token=token)

    sessao, access, refresh = create_session(
        db,
        usuario,
        empresa_id,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    usuario.ultimo_login_em = now
    db.commit()
    return LoginResponse(
        status="AUTHENTICATED",
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/mfa/setup", response_model=MFASetupResponse)
def mfa_setup(preauth_token: str, db: Session = Depends(get_db)):
    usuario, _ = _usuario_por_preauth(db, preauth_token, "mfa_setup")
    secret = generate_secret()
    usuario.mfa_secret_enc = encrypt_secret(secret)
    usuario.mfa_habilitado = False
    usuario.mfa_confirmado_em = None
    db.commit()
    return MFASetupResponse(
        secret=secret,
        provisioning_uri=provisioning_uri(secret, usuario.email),
    )


@router.post("/mfa/verify", response_model=LoginResponse)
def mfa_verify(
    dados: MFAVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        payload = decode_token(dados.preauth_token, "preauth")
        purpose = payload.get("purpose")
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token de pré-autenticação inválido ou expirado.",
        )

    if purpose not in {"mfa_setup", "mfa_verify"}:
        raise HTTPException(status_code=401, detail="Finalidade MFA inválida.")

    usuario, empresa_id = _usuario_por_preauth(
        db,
        dados.preauth_token,
        purpose,
    )

    if not usuario.mfa_secret_enc:
        raise HTTPException(status_code=409, detail="MFA ainda não configurado.")

    secret = decrypt_secret(usuario.mfa_secret_enc)
    if not verify_totp(secret, dados.codigo):
        raise HTTPException(status_code=401, detail="Código MFA inválido.")

    if purpose == "mfa_setup":
        usuario.mfa_habilitado = True
        usuario.mfa_confirmado_em = utcnow()

    sessao, access, refresh = create_session(
        db,
        usuario,
        empresa_id,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    usuario.ultimo_login_em = utcnow()
    db.commit()

    return LoginResponse(
        status="AUTHENTICATED",
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh(dados: RefreshRequest, db: Session = Depends(get_db)):
    fingerprint = refresh_token_fingerprint(dados.refresh_token)
    nova_sessao, access, novo_refresh, motivo = rotate_refresh_session(
        db,
        dados.refresh_token,
    )

    if motivo:
        # O token puro nunca é gravado em log.
        logger.warning(
            "refresh_rejected reason=%s fingerprint=%s",
            motivo,
            fingerprint,
        )
        raise HTTPException(
            status_code=401,
            detail="Refresh token inválido ou expirado.",
        )

    db.commit()
    logger.info(
        "refresh_rotated session_id=%s fingerprint=%s",
        nova_sessao.id,
        fingerprint,
    )
    return LoginResponse(
        status="AUTHENTICATED",
        access_token=access,
        refresh_token=novo_refresh,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/logout")
def logout(
    dados: LogoutRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    sessao = context["sessao"]
    revoke_session(sessao, "LOGOUT")
    db.commit()
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def me(context=Depends(get_current_context), db: Session = Depends(get_db)):
    usuario = context["usuario"]
    vinculo = context["vinculo"]
    perfil = vinculo.perfil.codigo if vinculo else None

    permissoes = []
    if usuario.is_superadmin:
        permissoes = ["*"]
    elif vinculo:
        rows = db.query(PerfilPermissao).filter(
            PerfilPermissao.perfil_id == vinculo.perfil_id
        ).all()
        permissoes = sorted(
            [r.permissao.codigo for r in rows if r.permissao.ativo]
        )

    return MeResponse(
        id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        is_superadmin=usuario.is_superadmin,
        empresa_id=context["empresa_id"],
        perfil=perfil,
        permissoes=permissoes,
    )
