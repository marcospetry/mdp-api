"""Sincronizacao de comentarios por consulta (Instagram).

Por que existe: a Meta so entrega webhooks de COMENTARIOS com Acesso Avancado. Enquanto a revisao nao aprova, a consulta
(GET /<media>/comments) funciona com Acesso Padrao. Os dois caminhos gravam no mesmo lugar e se completam.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import meta_instagram, omni_connections, omni_store
from app.services.auth_service import utcnow

logger = logging.getLogger("mdp.omni.sync")
THROTTLE = timedelta(seconds=20)
MEDIA_LIMIT, COMMENT_LIMIT = 8, 30


def sync_instagram_comments(platform_db: Session, tenant_db: Session, tenant_id) -> dict:
    """Devolve {'new': n, 'skipped': bool}. Nunca levanta erro por falha da Meta (so registra um codigo curto)."""
    conn = omni_connections.get_connection(platform_db, tenant_id, "INSTAGRAM")
    if not conn or conn["status"] not in omni_connections.ACTIVE or not conn["ig_id"]:
        return {"new": 0, "skipped": True}
    now = utcnow()
    last = (conn["metadados"] or {}).get("last_comment_sync")
    if last:
        try:
            from datetime import datetime
            if now - datetime.fromisoformat(last) < THROTTLE:
                return {"new": 0, "skipped": True}
        except ValueError:
            pass
    creds = omni_connections.get_credentials(platform_db, conn["endpoint_id"])
    if not creds:
        return {"new": 0, "skipped": True}
    own = (creds["username"] or "").lower()
    new = 0
    try:
        for media in meta_instagram.list_media(creds["token"], creds["ig_id"], MEDIA_LIMIT):
            for c in meta_instagram.list_comments(creds["token"], media["id"], COMMENT_LIMIT):
                if not c.get("id") or (own and str(c.get("username", "")).lower() == own):
                    continue
                if omni_store.store_comment(
                    tenant_db, endpoint_id=conn["endpoint_id"], comment_id=str(c["id"]), media_id=str(media["id"]), parent_id=None,
                    body=c.get("text"), author_id=None, author_username=c.get("username"), ts=omni_store.to_datetime(c.get("timestamp")),
                    post_resumo=media.get("caption"), post_permalink=media.get("permalink"),
                ):
                    new += 1
    except meta_instagram.MetaApiError as exc:
        logger.warning("sync_comments_falhou tenant=%s code=%s", tenant_id, exc.code)
        platform_db.execute(text("UPDATE canal_conexoes SET ultimo_erro = :e, ultimo_erro_em = :n WHERE id = :id"),
                            {"e": f"sync:{exc.code}"[:200], "n": now, "id": str(conn["conexao_id"])})
        platform_db.commit()
        return {"new": new, "skipped": False, "error": exc.code}
    platform_db.execute(text("""UPDATE canal_conexoes SET metadados = metadados || CAST(:m AS jsonb) WHERE id = :id"""),
                        {"m": json.dumps({"last_comment_sync": now.isoformat()}), "id": str(conn["conexao_id"])})
    platform_db.commit()
    return {"new": new, "skipped": False}
