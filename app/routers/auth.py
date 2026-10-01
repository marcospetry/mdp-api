from uuid import UUID
import logging
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_platform_db, tenant_session
from app.security.dependencies import get_authorized_tenant_db
from app.models.auth import PerfilPermissao
from app.models.platform_auth import PlatformTenant, PlatformUsuario
from app.schemas.auth import LoginRequest, LoginResponse, LogoutRequest, MFASetupResponse, MFAVerifyRequest, MeResponse, RefreshRequest
from app.security.dependencies import get_current_context
from app.security.jwt import create_preauth_token, decode_token
from app.security.mfa import decrypt_secret, encrypt_secret, generate_secret, provisioning_uri, verify_totp
from app.security.password import verify_password
from app.services.auth_service import create_session, refresh_token_fingerprint, resolve_empresa_tenant, resolve_tenant, revoke_session, rotate_refresh_session, utcnow

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])
logger = logging.getLogger("mdp.auth")


def _usuario_por_preauth(db: Session, token: str, purpose: str):
    try:
        payload = decode_token(token, "preauth")
        if payload.get("purpose") != purpose:
            raise jwt.InvalidTokenError("Finalidade inválida")
        usuario = db.query(PlatformUsuario).filter(
            PlatformUsuario.id == UUID(payload["sub"]), PlatformUsuario.ativo.is_(True)
        ).first()
        if not usuario:
            raise jwt.InvalidTokenError("Usuário inválido")
        return usuario, UUID(payload["tenant_id"]) if payload.get("tenant_id") else None
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token de pré-autenticação inválido ou expirado.")


@router.post("/login", response_model=LoginResponse)
def login(dados: LoginRequest, request: Request, db: Session = Depends(get_platform_db)):
    usuario = db.query(PlatformUsuario).filter(PlatformUsuario.email == dados.email.lower().strip()).first()
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
    # Um unico tenant autorizado e selecionado automaticamente, inclusive
    # para SUPERADMIN. Acesso exclusivamente a Plataforma e explicito.
    if usuario.is_superadmin and dados.contexto_plataforma:
        if dados.tenant_id is not None:
            raise HTTPException(status_code=422, detail="Selecione Plataforma ou tenant, nao ambos.")
        tenant_id, vinculo = None, None
    else:
        tenant_id, vinculo = resolve_tenant(db, usuario, dados.tenant_id)
        if usuario.is_superadmin and tenant_id is None and vinculo is None and dados.tenant_id is None:
            # SUPERADMIN sem vinculo operacional permanece na Plataforma.
            tenant_id, vinculo = None, None
    if vinculo == "MULTIPLOS_TENANTS":
        db.commit()
        raise HTTPException(status_code=409, detail="Informe tenant_id para selecionar o Tenant ativo.")
    if not tenant_id and not usuario.is_superadmin:
        db.commit()
        raise HTTPException(status_code=403, detail="Usuário sem Tenant ativo autorizado.")

    mfa_obrigatorio = usuario.is_superadmin or usuario.mfa_habilitado
    if mfa_obrigatorio:
        purpose = "mfa_verify" if usuario.mfa_habilitado and usuario.mfa_secret_enc else "mfa_setup"
        token = create_preauth_token(usuario.id, tenant_id, purpose)
        db.commit()
        return LoginResponse(status=purpose.upper(), preauth_token=token)

    raise HTTPException(status_code=409, detail="Fluxo sem MFA ainda não habilitado para a arquitetura Platform/Tenant.")


@router.post("/mfa/setup", response_model=MFASetupResponse)
def mfa_setup(preauth_token: str, db: Session = Depends(get_platform_db)):
    usuario, _ = _usuario_por_preauth(db, preauth_token, "mfa_setup")
    secret = generate_secret()
    usuario.mfa_secret_enc = encrypt_secret(secret)
    usuario.mfa_habilitado = False
    usuario.mfa_confirmado_em = None
    db.commit()
    return MFASetupResponse(secret=secret, provisioning_uri=provisioning_uri(secret, usuario.email))


@router.post("/mfa/verify", response_model=LoginResponse)
def mfa_verify(dados: MFAVerifyRequest, request: Request, platform_db: Session = Depends(get_platform_db)):
    try:
        payload = decode_token(dados.preauth_token, "preauth")
        purpose = payload.get("purpose")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token de pré-autenticação inválido ou expirado.")
    if purpose not in {"mfa_setup", "mfa_verify"}:
        raise HTTPException(status_code=401, detail="Finalidade MFA inválida.")

    usuario, tenant_id = _usuario_por_preauth(platform_db, dados.preauth_token, purpose)
    if not usuario.mfa_secret_enc:
        raise HTTPException(status_code=409, detail="MFA ainda não configurado.")
    if not verify_totp(decrypt_secret(usuario.mfa_secret_enc), dados.codigo):
        raise HTTPException(status_code=401, detail="Código MFA inválido.")
    if purpose == "mfa_setup":
        usuario.mfa_habilitado = True
        usuario.mfa_confirmado_em = utcnow()

    if tenant_id is None:
        if not usuario.is_superadmin:
            raise HTTPException(status_code=403, detail="Acesso à Plataforma não autorizado.")
        empresa_id = None
    else:
        if not resolve_tenant(platform_db, usuario, tenant_id)[1]:
            raise HTTPException(status_code=403, detail="Tenant não autorizado.")
        with tenant_session(platform_db, tenant_id) as tenant_db:
            empresa_id, _, local = resolve_empresa_tenant(tenant_db, usuario.id)
        if not local:
            raise HTTPException(status_code=403, detail="Usuário não provisionado no Tenant.")
    sessao, access, refresh = create_session(platform_db, usuario, tenant_id, empresa_id, request.client.host if request.client else None, request.headers.get("user-agent"))
    usuario.ultimo_login_em = utcnow()
    platform_db.commit()
    return LoginResponse(status="AUTHENTICATED", access_token=access, refresh_token=refresh, expires_in=settings.access_token_minutes * 60)


@router.post("/refresh", response_model=LoginResponse)
def refresh(dados: RefreshRequest, platform_db: Session = Depends(get_platform_db)):
    fingerprint = refresh_token_fingerprint(dados.refresh_token)
    nova_sessao, access, novo_refresh, motivo = rotate_refresh_session(platform_db, dados.refresh_token)
    if motivo:
        logger.warning("refresh_rejected reason=%s fingerprint=%s", motivo, fingerprint)
        raise HTTPException(status_code=401, detail="Refresh token inválido ou expirado.")
    platform_db.commit()
    logger.info("refresh_rotated session_id=%s fingerprint=%s", nova_sessao.id, fingerprint)
    return LoginResponse(status="AUTHENTICATED", access_token=access, refresh_token=novo_refresh, expires_in=settings.access_token_minutes * 60)


@router.post("/logout")
def logout(dados: LogoutRequest, context=Depends(get_current_context), db: Session = Depends(get_platform_db)):
    from app.models.platform_auth import PlatformSessaoUsuario
    sessao = db.query(PlatformSessaoUsuario).filter(PlatformSessaoUsuario.id == context["sessao"].id).first()
    if sessao:
        revoke_session(sessao, "LOGOUT")
        db.commit()
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def me(
    context=Depends(get_current_context),
    platform_db: Session = Depends(get_platform_db),
):
    usuario = context["usuario"]
    vinculo = context["vinculo"]
    perfil = vinculo.perfil.codigo if vinculo else ("SUPERADMIN" if context["tenant_id"] is None else None)
    permissoes = []
    if context["tenant_id"] is None and usuario.is_superadmin:
        permissoes = ["PLATAFORMA_ADMIN"]
    elif vinculo and vinculo.perfil.acesso_total:
        permissoes = ["*"]
    elif vinculo:
        with tenant_session(platform_db, context["tenant_id"]) as tenant_db:
            rows = tenant_db.query(PerfilPermissao).filter(PerfilPermissao.perfil_id == vinculo.perfil_id).all()
            permissoes = sorted([r.permissao.codigo for r in rows if r.permissao.ativo])
    tenant = None
    if context["tenant_id"] is not None:
        tenant = platform_db.query(PlatformTenant).filter(
            PlatformTenant.id == context["tenant_id"],
            PlatformTenant.ativo.is_(True),
        ).first()
    return MeResponse(
        id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        is_superadmin=usuario.is_superadmin,
        empresa_id=context["empresa_id"],
        tenant_id=context["tenant_id"],
        tenant_nome=tenant.nome if tenant else None,
        contexto_tipo=context["contexto_tipo"],
        perfil=perfil,
        permissoes=permissoes,
    )
