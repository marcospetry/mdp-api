"""
Teste automático do mecanismo de sessão/refresh/logout da MDP API.

Não pede senha.
Não pede MFA.
Não imprime access token nem refresh token.
Usa um usuário superadmin já existente.
Cria sessões temporárias de teste e remove-as ao final.

Executar com o túnel SSH para o PostgreSQL MDP ativo:
    python scripts\test_auth_session.py
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal
from app.models.auth import SessaoUsuario, Usuario, UsuarioEmpresa
from app.services.auth_service import (
    create_session,
    hash_refresh_token,
    revoke_session,
    rotate_refresh_session,
)


def fail(msg: str):
    raise AssertionError(msg)


def main():
    db = SessionLocal()
    test_session_ids = []

    try:
        usuario = db.query(Usuario).filter(
            Usuario.is_superadmin.is_(True),
            Usuario.ativo.is_(True),
        ).first()

        if not usuario:
            fail("Nenhum superadmin ativo encontrado para o teste.")

        vinculo = db.query(UsuarioEmpresa).filter(
            UsuarioEmpresa.usuario_id == usuario.id,
            UsuarioEmpresa.ativo.is_(True),
        ).first()

        empresa_id = vinculo.empresa_id if vinculo else None

        # 1. Cria sessão temporária e confirma persistência do hash.
        sessao1, _, refresh1 = create_session(
            db,
            usuario,
            empresa_id,
            "127.0.0.1",
            "MDP-AUTH-AUTO-TEST",
        )
        db.commit()
        db.refresh(sessao1)
        test_session_ids.append(sessao1.id)

        if sessao1.refresh_token_hash != hash_refresh_token(refresh1):
            fail("Hash do refresh criado não corresponde ao token retornado.")

        # 2. Rotaciona o refresh token.
        sessao2, _, refresh2, motivo = rotate_refresh_session(db, refresh1)
        if motivo:
            fail(f"Rotação do refresh falhou: {motivo}")

        db.commit()
        db.refresh(sessao1)
        db.refresh(sessao2)
        test_session_ids.append(sessao2.id)

        if sessao1.revogada_em is None:
            fail("Sessão antiga não foi revogada durante a rotação.")

        if sessao1.motivo_revogacao != "ROTACAO_REFRESH":
            fail("Motivo de revogação da sessão antiga está incorreto.")

        if sessao2.refresh_token_hash != hash_refresh_token(refresh2):
            fail("Hash do novo refresh não corresponde ao token retornado.")

        # 3. Token antigo deve ser rejeitado como revogado.
        _, _, _, motivo_antigo = rotate_refresh_session(db, refresh1)
        if motivo_antigo != "REVOKED":
            fail(
                "Refresh antigo deveria retornar REVOKED, "
                f"mas retornou {motivo_antigo!r}."
            )

        # 4. Simula logout da sessão nova.
        revoke_session(sessao2, "LOGOUT_TEST")
        db.commit()
        db.refresh(sessao2)

        if sessao2.revogada_em is None:
            fail("Logout não marcou a sessão como revogada.")

        if sessao2.motivo_revogacao != "LOGOUT_TEST":
            fail("Motivo de logout não foi persistido.")

        print("AUTH SESSION TEST: OK")
        print("create_session: OK")
        print("refresh hash: OK")
        print("refresh rotation: OK")
        print("old refresh rejection: OK")
        print("logout/revocation: OK")

    finally:
        # Remove somente sessões temporárias criadas por este teste.
        if test_session_ids:
            db.query(SessaoUsuario).filter(
                SessaoUsuario.id.in_(test_session_ids)
            ).delete(synchronize_session=False)
            db.commit()
        db.close()


if __name__ == "__main__":
    main()
