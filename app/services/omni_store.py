"""Gravacao dos eventos recebidos do Instagram no banco do TENANT (conversas, mensagens, comentarios).

Idempotente: a Meta reenvia eventos que falham, entao toda gravacao ignora duplicatas (mid / id do comentario).
Nunca registra o conteudo das mensagens em log.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session


def to_datetime(value) -> datetime:
    """Aceita epoch em segundos ou milissegundos, ou texto ISO ('2017-08-31T19:16:02+0000')."""
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            v = float(value)
            return datetime.fromtimestamp(v / 1000 if v > 1e12 else v, tz=timezone.utc)
        if isinstance(value, str) and value:
            return datetime.strptime(value.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
    except (ValueError, OverflowError, OSError):
        pass
    return datetime.now(timezone.utc)


def store_incoming_dm(db: Session, *, endpoint_id, sender_id: str, mid: str, body: str | None, tipo: str, ts: datetime) -> dict:
    """Grava uma mensagem recebida. Devolve {inserted, conversa_id, needs_profile}."""
    conv = db.execute(text("""
        INSERT INTO omni_conversas (canal, endpoint_id, participante_externo_id, ultima_mensagem_em, ultima_mensagem_cliente_em, nao_lidas)
        VALUES ('INSTAGRAM', :ep, :sid, :ts, :ts, 0)
        ON CONFLICT (endpoint_id, participante_externo_id) DO UPDATE SET status = 'ABERTA'
        RETURNING id, (participante_nome IS NULL AND participante_usuario IS NULL) AS needs_profile
    """), {"ep": str(endpoint_id), "sid": sender_id, "ts": ts}).mappings().first()
    inserted = db.execute(text("""
        INSERT INTO omni_mensagens (conversa_id, direcao, external_message_id, tipo, texto, status_envio, ocorrida_em)
        VALUES (:cv, 'ENTRADA', :mid, :tipo, :texto, 'RECEBIDA', :ts)
        ON CONFLICT (conversa_id, external_message_id) WHERE external_message_id IS NOT NULL DO NOTHING
        RETURNING id
    """), {"cv": str(conv["id"]), "mid": mid, "tipo": tipo, "texto": body, "ts": ts}).first()
    if inserted:
        db.execute(text("""
            UPDATE omni_conversas SET nao_lidas = nao_lidas + 1,
                   ultima_mensagem_em = GREATEST(COALESCE(ultima_mensagem_em, :ts), :ts),
                   ultima_mensagem_cliente_em = GREATEST(COALESCE(ultima_mensagem_cliente_em, :ts), :ts),
                   updated_at = now()
             WHERE id = :cv
        """), {"cv": str(conv["id"]), "ts": ts})
    db.commit()
    return {"inserted": bool(inserted), "conversa_id": str(conv["id"]), "needs_profile": bool(conv["needs_profile"])}


def set_profile(db: Session, conversa_id: str, name: str | None, username: str | None) -> None:
    db.execute(text("""UPDATE omni_conversas SET participante_nome = COALESCE(:n, participante_nome),
                       participante_usuario = COALESCE(:u, participante_usuario) WHERE id = :id"""),
               {"n": name, "u": username, "id": conversa_id})
    db.commit()


def store_comment(db: Session, *, endpoint_id, comment_id: str, media_id: str | None, parent_id: str | None, body: str | None,
                  author_id: str | None, author_username: str | None, ts: datetime,
                  post_resumo: str | None = None, post_permalink: str | None = None) -> bool:
    row = db.execute(text("""
        INSERT INTO omni_comentarios (canal, endpoint_id, external_comment_id, parent_external_id, post_external_id, post_resumo, post_permalink,
                                      origem, autor_externo_id, autor_nome, autor_usuario, texto, ocorrido_em)
        VALUES ('INSTAGRAM', :ep, :cid, :parent, :media, :resumo, :link, 'EXTERNO', :aid, :nome, :usr, :texto, :ts)
        ON CONFLICT (endpoint_id, external_comment_id) DO NOTHING
        RETURNING id
    """), {"ep": str(endpoint_id), "cid": comment_id, "parent": parent_id, "media": media_id,
           "resumo": (post_resumo or None) and post_resumo[:300], "link": post_permalink, "aid": author_id,
           "nome": author_username, "usr": author_username, "texto": body, "ts": ts}).first()
    db.commit()
    return bool(row)


def known_post(db: Session, endpoint_id, media_id: str) -> dict | None:
    row = db.execute(text("""SELECT post_resumo, post_permalink FROM omni_comentarios
                             WHERE endpoint_id = :ep AND post_external_id = :m AND (post_resumo IS NOT NULL OR post_permalink IS NOT NULL) LIMIT 1"""),
                     {"ep": str(endpoint_id), "m": media_id}).mappings().first()
    return dict(row) if row else None
