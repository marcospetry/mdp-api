"""Limpa as CONVERSAS, MENSAGENS e COMENTARIOS do Omni de um tenant de DEMONSTRACAO (ex.: MDP_DEMO).

Para que serve: deixar a Caixa de entrada e os Comentarios vazios antes de gravar os videos do App Review.

O que apaga (somente no banco do tenant informado):
  - omni_comentarios, omni_conversas e, em cascata, omni_mensagens.
O que NAO toca:
  - conexoes (canal_conexoes), canais (tenant_endpoints), usuarios, tokens e qualquer outra tabela.
  - Instagram/Facebook continuam conectados; so o historico some. Novos eventos voltam a aparecer normalmente.

Seguranca:
  - Recusa tenant de sistema (dados reais) e qualquer tenant cujo codigo nao contenha "DEMO".
  - Dry-run por padrao: so mostra as contagens e nao altera nada.
  - Com --executar, pede para digitar uma frase exata. Exige terminal interativo.
  - Imprime so contagens, nunca o conteudo das mensagens.

Uso (na raiz do projeto, com o ambiente da API):
    python scripts/limpar_omni_demo.py --tenant-codigo MDP_DEMO                       # mostra o que seria apagado
    python scripts/limpar_omni_demo.py --tenant-codigo MDP_DEMO --canal FACEBOOK      # so o Facebook
    python scripts/limpar_omni_demo.py --tenant-codigo MDP_DEMO --executar            # apaga (pede confirmacao)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

CANAIS = ("INSTAGRAM", "FACEBOOK")


def contar(db, canal: str | None) -> dict:
    """Contagens por canal (e total) do que seria apagado. canal=None conta todos."""
    params = {"canal": canal}
    por_canal = {}
    for c in CANAIS:
        if canal and canal != c:
            continue
        conversas = db.execute(text("SELECT count(*) FROM omni_conversas WHERE canal = :c"), {"c": c}).scalar() or 0
        mensagens = db.execute(
            text("SELECT count(*) FROM omni_mensagens m JOIN omni_conversas v ON v.id = m.conversa_id WHERE v.canal = :c"),
            {"c": c}).scalar() or 0
        comentarios = db.execute(text("SELECT count(*) FROM omni_comentarios WHERE canal = :c"), {"c": c}).scalar() or 0
        por_canal[c] = {"conversas": conversas, "mensagens": mensagens, "comentarios": comentarios}
    # linhas de canais fora da lista (nao deveria haver, o CHECK impede) entram no total do filtro TODOS
    if not canal:
        extra = db.execute(text("SELECT count(*) FROM omni_conversas WHERE canal <> ALL(:l)"), {"l": list(CANAIS)}).scalar() or 0
        if extra:
            por_canal["OUTROS"] = {"conversas": extra, "mensagens": 0, "comentarios": 0}
    total = {k: sum(v[k] for v in por_canal.values()) for k in ("conversas", "mensagens", "comentarios")}
    return {"por_canal": por_canal, "total": total, "filtro": params["canal"] or "TODOS"}


def apagar(db, canal: str | None) -> dict:
    """Apaga comentarios e conversas (mensagens saem junto, ON DELETE CASCADE). Uma transacao so."""
    filtro = "(CAST(:canal AS text) IS NULL OR canal = :canal)"
    try:
        comentarios = db.execute(text(f"DELETE FROM omni_comentarios WHERE {filtro}"), {"canal": canal}).rowcount
        conversas = db.execute(text(f"DELETE FROM omni_conversas WHERE {filtro}"), {"canal": canal}).rowcount
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"conversas": conversas, "comentarios": comentarios}


def _imprimir(c: dict) -> None:
    print(f"  {'canal':<10} {'conversas':>10} {'mensagens':>10} {'comentarios':>12}")
    for nome, v in c["por_canal"].items():
        print(f"  {nome:<10} {v['conversas']:>10} {v['mensagens']:>10} {v['comentarios']:>12}")
    t = c["total"]
    print(f"  {'TOTAL':<10} {t['conversas']:>10} {t['mensagens']:>10} {t['comentarios']:>12}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tenant-codigo", required=True)
    ap.add_argument("--canal", choices=("INSTAGRAM", "FACEBOOK", "TODOS"), default="TODOS")
    ap.add_argument("--executar", action="store_true")
    a = ap.parse_args()
    canal = None if a.canal == "TODOS" else a.canal

    from app.database import PlatformSessionLocal, tenant_session
    from app.models.platform_auth import PlatformTenant

    platform_db = PlatformSessionLocal()
    try:
        tenant = platform_db.query(PlatformTenant).filter(PlatformTenant.codigo == a.tenant_codigo).first()
        if not tenant:
            sys.exit("Tenant nao encontrado.")
        if getattr(tenant, "tenant_sistema", False):
            sys.exit("Recusado: tenant de sistema (dados reais). Use somente tenants de demonstracao.")
        if "DEMO" not in tenant.codigo.upper():
            sys.exit("Recusado: o codigo do tenant nao contem DEMO. Este script e so para tenants de demonstracao.")
        print(f"Tenant {tenant.codigo} | canal: {a.canal} | modo: {'EXECUCAO' if a.executar else 'DRY-RUN (nada alterado)'}")
        with tenant_session(platform_db, tenant.id) as db:
            antes = contar(db, canal)
            print("Seria apagado:" if not a.executar else "Sera apagado:")
            _imprimir(antes)
            if not a.executar:
                print("Nada foi alterado. Para apagar, rode de novo com --executar.")
                return
            if antes["total"]["conversas"] == 0 and antes["total"]["comentarios"] == 0:
                print("Nao ha nada para apagar.")
                return
            if not sys.stdin.isatty():
                sys.exit("Recusado: a confirmacao exige um terminal interativo.")
            frase = f"LIMPAR {tenant.codigo} {a.canal}"
            print(f'Para confirmar, digite exatamente: {frase}')
            if input("> ").strip() != frase:
                sys.exit("Confirmacao diferente do esperado. Nada foi alterado.")
            resultado = apagar(db, canal)
            depois = contar(db, canal)
            print(f"Apagado: {resultado['conversas']} conversas (e suas mensagens), {resultado['comentarios']} comentarios.")
            print("Restante:")
            _imprimir(depois)
    finally:
        platform_db.close()


if __name__ == "__main__":
    main()
