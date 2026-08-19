"""
Teste automático do hotfix de proteção dos CRUDs do Diagnóstico.

Pré-requisitos:
- API local rodando em http://127.0.0.1:8000
- túnel SSH ativo para o PostgreSQL oficial
- ambiente virtual da MDP API ativo

Não pede senha.
Não pede MFA.
Não imprime tokens.
Cria uma sessão temporária de teste e remove ao final.

Executar:
    python scripts\test_protecao_diagnostico.py
"""

from pathlib import Path
import sys
import urllib.error
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal
from app.models.auth import SessaoUsuario, Usuario, UsuarioEmpresa
from app.services.auth_service import create_session

BASE_URL = "http://127.0.0.1:8000"


def get_status(path: str, token: str | None = None) -> tuple[int, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        headers=headers,
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body


def main():
    db = SessionLocal()
    sessao_id = None

    try:
        usuario = (
            db.query(Usuario)
            .filter(
                Usuario.is_superadmin.is_(True),
                Usuario.ativo.is_(True),
            )
            .first()
        )

        if not usuario:
            raise RuntimeError("Nenhum superadmin ativo encontrado.")

        vinculo = (
            db.query(UsuarioEmpresa)
            .filter(
                UsuarioEmpresa.usuario_id == usuario.id,
                UsuarioEmpresa.ativo.is_(True),
            )
            .first()
        )

        empresa_id = vinculo.empresa_id if vinculo else None

        # 1. Categorias sem autenticação.
        status, _ = get_status("/api/diagnostico/categorias")
        if status != 401:
            raise AssertionError(
                f"Categorias sem login: esperado 401, recebido {status}."
            )

        # 2. Cria sessão temporária e access token válido.
        sessao, access_token, _ = create_session(
            db,
            usuario,
            empresa_id,
            "127.0.0.1",
            "MDP-PROTECTED-ROUTES-TEST",
        )
        db.commit()
        db.refresh(sessao)
        sessao_id = sessao.id

        # 3. Categorias autenticado.
        status, body = get_status(
            "/api/diagnostico/categorias",
            access_token,
        )
        if status != 200:
            raise AssertionError(
                f"Categorias autenticado: esperado 200, recebido {status}. "
                f"Resposta: {body[:300]}"
            )

        # 4. Formulários sem autenticação.
        status, _ = get_status("/api/diagnostico/formularios")
        if status != 401:
            raise AssertionError(
                f"Formulários sem login: esperado 401, recebido {status}."
            )

        # 5. Formulários autenticado.
        status, body = get_status(
            "/api/diagnostico/formularios",
            access_token,
        )
        if status != 200:
            raise AssertionError(
                f"Formulários autenticado: esperado 200, recebido {status}. "
                f"Resposta: {body[:300]}"
            )

        print("PROTECAO DIAGNOSTICO: OK")
        print("categorias sem login: 401 OK")
        print("categorias autenticado: 200 OK")
        print("formularios sem login: 401 OK")
        print("formularios autenticado: 200 OK")

    finally:
        if sessao_id is not None:
            db.query(SessaoUsuario).filter(
                SessaoUsuario.id == sessao_id
            ).delete(synchronize_session=False)
            db.commit()

        db.close()


if __name__ == "__main__":
    main()
