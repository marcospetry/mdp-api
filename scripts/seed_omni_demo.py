"""Dados de EXEMPLO do Omni (conversas, mensagens e comentarios) para um tenant de demonstracao.

SOMENTE para tenants de teste (ex.: MDP_DEMO). Recusa tenants de sistema (MDP) e qualquer tenant
cujo codigo nao seja informado. Nao toca em dados reais. Idempotente. Dry-run por padrao.

Os registros usam IDs externos com prefixo "sample-" e endpoint_id ficticios, entao sao
facilmente identificaveis e removiveis (--remover).

Uso (na raiz do projeto, com o .venv ativo):
    python scripts/seed_omni_demo.py --tenant-codigo MDP_DEMO              # mostra o plano
    python scripts/seed_omni_demo.py --tenant-codigo MDP_DEMO --executar   # cria
    python scripts/seed_omni_demo.py --tenant-codigo MDP_DEMO --remover --executar
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

EP_IG = "00000000-0000-4000-8000-0000000000a1"
EP_FB = "00000000-0000-4000-8000-0000000000a2"


def _ts(minutes_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)


def seed(db) -> dict:
    """Cria os dados de exemplo (idempotente). Retorna contagens inseridas."""
    conv_rows = [
        # canal, endpoint, participante, nome, usuario, nao_lidas, ultima_msg_min, ultima_cliente_min
        ("INSTAGRAM", EP_IG, "sample-ig-1", "Maria S.", "maria.s", 1, 2, 2),
        ("FACEBOOK", EP_FB, "sample-fb-1", "João P.", None, 0, 60, 70),
        ("INSTAGRAM", EP_IG, "sample-ig-2", "Ana C.", "ana.costa", 0, 1800, 1800),  # janela de 24h fechada
    ]
    msgs = {
        "sample-ig-1": [("ENTRADA", "Hi! Do you have availability this week?", 4),
                        ("SAIDA", "Hello Maria! Yes, we have openings on Thursday and Friday. Which works better for you?", 3),
                        ("ENTRADA", "Thursday morning, please.", 2)],
        "sample-fb-1": [("SAIDA", "Your booking is confirmed for Friday.", 75), ("ENTRADA", "Thanks, see you Friday!", 60)],
        "sample-ig-2": [("ENTRADA", "What are your opening hours?", 1800)],
    }
    comments = [
        ("INSTAGRAM", EP_IG, "sample-c1", "sample-post-ig-1", "Spring promotion, book this week", "carla.mendes", "Carla M.", "Does this include weekends?", 5),
        ("FACEBOOK", EP_FB, "sample-c2", "sample-post-fb-1", "New opening hours", None, "Pedro L.", "Great news, thank you!", 60),
        ("INSTAGRAM", EP_IG, "sample-c3", "sample-post-ig-2", "Our services", "ana.costa", "Ana C.", "Where can I find the price list?", 1440),
    ]
    created = {"conversas": 0, "mensagens": 0, "comentarios": 0}
    for canal, ep, ext, nome, usuario, unread, last_min, cli_min in conv_rows:
        r = db.execute(text("""
            INSERT INTO omni_conversas (canal, endpoint_id, participante_externo_id, participante_nome, participante_usuario,
                                        nao_lidas, ultima_mensagem_em, ultima_mensagem_cliente_em)
            VALUES (:c, :ep, :ext, :n, :u, :nl, :lm, :lc)
            ON CONFLICT (endpoint_id, participante_externo_id) DO NOTHING RETURNING id
        """), {"c": canal, "ep": ep, "ext": ext, "n": nome, "u": usuario, "nl": unread, "lm": _ts(last_min), "lc": _ts(cli_min)}).first()
        if not r:
            continue
        created["conversas"] += 1
        for i, (direcao, texto, mins) in enumerate(msgs[ext], start=1):
            db.execute(text("""
                INSERT INTO omni_mensagens (conversa_id, direcao, external_message_id, texto, status_envio, ocorrida_em)
                VALUES (:cv, :d, :x, :t, :s, :at)
                ON CONFLICT (conversa_id, external_message_id) WHERE external_message_id IS NOT NULL DO NOTHING
            """), {"cv": str(r[0]), "d": direcao, "x": f"{ext}-m{i}", "t": texto,
                   "s": "RECEBIDA" if direcao == "ENTRADA" else "ENVIADA", "at": _ts(mins)})
            created["mensagens"] += 1
    for canal, ep, ext, post, resumo, usuario, nome, texto, mins in comments:
        r = db.execute(text("""
            INSERT INTO omni_comentarios (canal, endpoint_id, external_comment_id, post_external_id, post_resumo, origem,
                                          autor_usuario, autor_nome, texto, respondido, ocorrido_em)
            VALUES (:c, :ep, :x, :p, :r, 'EXTERNO', :u, :n, :t, :resp, :at)
            ON CONFLICT (endpoint_id, external_comment_id) DO NOTHING RETURNING id
        """), {"c": canal, "ep": ep, "x": ext, "p": post, "r": resumo, "u": usuario, "n": nome, "t": texto,
               "resp": ext == "sample-c2", "at": _ts(mins)}).first()
        if r:
            created["comentarios"] += 1
            if ext == "sample-c2":  # um comentario ja respondido, para mostrar o estado
                db.execute(text("""
                    INSERT INTO omni_comentarios (canal, endpoint_id, external_comment_id, parent_external_id, post_external_id,
                                                  origem, texto, status_envio, ocorrido_em)
                    VALUES (:c, :ep, 'sample-c2-r1', 'sample-c2', :p, 'PROPRIO', 'Thank you, Pedro! See you soon.', 'ENVIADA', :at)
                    ON CONFLICT (endpoint_id, external_comment_id) DO NOTHING
                """), {"c": canal, "ep": ep, "p": post, "at": _ts(55)})
    db.commit()
    return created


def remove(db) -> dict:
    n1 = db.execute(text("DELETE FROM omni_conversas WHERE endpoint_id IN (:a, :b)"), {"a": EP_IG, "b": EP_FB}).rowcount
    n2 = db.execute(text("DELETE FROM omni_comentarios WHERE endpoint_id IN (:a, :b)"), {"a": EP_IG, "b": EP_FB}).rowcount
    db.commit()
    return {"conversas": n1, "comentarios": n2}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tenant-codigo", required=True)
    ap.add_argument("--remover", action="store_true")
    ap.add_argument("--executar", action="store_true")
    a = ap.parse_args()

    from app.database import PlatformSessionLocal, tenant_session
    from app.models.platform_auth import PlatformTenant

    platform_db = PlatformSessionLocal()
    try:
        tenant = platform_db.query(PlatformTenant).filter(PlatformTenant.codigo == a.tenant_codigo).first()
        if not tenant:
            sys.exit("Tenant nao encontrado.")
        if getattr(tenant, "tenant_sistema", False):
            sys.exit("Recusado: tenant de sistema (dados reais). Use somente tenants de demonstracao.")
        acao = "REMOVER dados de exemplo" if a.remover else "CRIAR dados de exemplo (3 conversas, 6 mensagens, 3 comentarios + 1 resposta)"
        print(f"Tenant {tenant.codigo}: {acao} | modo: {'EXECUCAO' if a.executar else 'DRY-RUN (nada alterado)'}")
        if not a.executar:
            return
        with tenant_session(platform_db, tenant.id) as db:
            print(remove(db) if a.remover else seed(db))
    finally:
        platform_db.close()


if __name__ == "__main__":
    main()
