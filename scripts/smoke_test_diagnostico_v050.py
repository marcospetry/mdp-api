"""Smoke test estático da API Diagnóstico v0.5.0.

Valida sem gravar dados:
- versão 0.5.0;
- presença dos endpoints de configuração esperados;
- todas as operações /api/diagnostico/* exigem esquema de segurança no OpenAPI;
- POST /api/contatos continua público.

Executar dentro do ambiente da API:
    python scripts/smoke_test_diagnostico_v050.py
"""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app

EXPECTED_PATHS = {
    "/api/diagnostico/metadados",
    "/api/diagnostico/categorias",
    "/api/diagnostico/perguntas",
    "/api/diagnostico/perguntas/{pergunta_id}/opcoes",
    "/api/diagnostico/perguntas/{pergunta_id}/faixas",
    "/api/diagnostico/faixas/{faixa_id}",
    "/api/diagnostico/formularios",
    "/api/diagnostico/formularios/{formulario_id}/perguntas",
    "/api/diagnostico/formularios/{formulario_id}/perguntas/ordenacao",
    "/api/diagnostico/formularios/{formulario_id}/regras-exibicao",
    "/api/diagnostico/regras-exibicao/{regra_id}",
}


def main():
    if app.version != "0.5.0":
        raise AssertionError(f"Versão esperada 0.5.0; encontrada {app.version}")

    schema = app.openapi()
    paths = schema.get("paths", {})

    faltantes = sorted(EXPECTED_PATHS - set(paths))
    if faltantes:
        raise AssertionError(f"Endpoints esperados ausentes: {faltantes}")

    inseguras = []
    for path, methods in paths.items():
        if not path.startswith("/api/diagnostico"):
            continue
        for method, spec in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not spec.get("security"):
                inseguras.append(f"{method.upper()} {path}")

    if inseguras:
        raise AssertionError(f"Rotas administrativas sem segurança OpenAPI: {inseguras}")

    contato_security = paths["/api/contatos"]["post"].get("security")
    if contato_security:
        raise AssertionError("POST /api/contatos deveria permanecer público.")

    print("MDP API 0.5.0 - SMOKE TEST: OK")
    print(f"Rotas /api/diagnostico protegidas: OK")
    print("POST /api/contatos público: OK")
    print("Endpoints de configuração esperados: OK")


if __name__ == "__main__":
    main()
