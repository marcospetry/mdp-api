"""Callbacks de privacidade da Meta (Instagram e Facebook) e pagina publica de status da exclusao de dados.

Rotas:
  POST /api/meta/deauthorize             -> a Meta avisa que o usuario removeu o app (revoga as conexoes)
  POST /api/meta/data-deletion           -> a Meta avisa que o usuario pediu exclusao (apaga os dados do canal)
  GET  /omni/data-deletion-status?code=  -> pagina publica, legivel, com a situacao do pedido

Seguranca: so aceita pedidos com `signed_request` valido (HMAC-SHA256 com o segredo do app); nao exige OMNI_META_ENABLED
(um pedido de exclusao deve ser atendido mesmo com a integracao desligada), mas responde 404 se nenhum segredo estiver configurado.
Nunca registra tokens, segredos nem conteudo de mensagens.
"""
from __future__ import annotations

import html
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import PlatformSessionLocal, tenant_session
from app.services import meta_privacy

logger = logging.getLogger("mdp.meta.privacy")
router = APIRouter(tags=["Meta privacy"])
MAX_BODY_BYTES = 20_000
SITE = "https://mdpconsultoria.com.br"


def _verified_user_id(raw: bytes, rota: str, content_type: str | None) -> str:
    secrets_list = meta_privacy.app_secrets()
    if not secrets_list:
        raise HTTPException(status_code=404, detail="Not found")
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    signed = meta_privacy.extract_signed_request(raw)
    payload = meta_privacy.parse_signed_request(signed, secrets_list)
    if payload is None:
        # so o motivo e nomes de campos: nunca o signed_request, o corpo nem segredos
        diag = meta_privacy.diagnose_signed_request(signed, secrets_list)
        logger.warning("meta_privacy_recusado rota=%s %s corpo_bytes=%d content_type=%s", rota,
                       " ".join(f"{k}={v}" for k, v in diag.items()), len(raw), (content_type or "")[:60])
        raise HTTPException(status_code=403, detail="Invalid signed_request")
    return payload["user_id"]


def _deauthorize(meta_user_id: str) -> dict:
    db = PlatformSessionLocal()
    try:
        return meta_privacy.handle_deauthorization(db, meta_user_id)
    finally:
        db.close()


def _delete_data(meta_user_id: str) -> dict:
    db = PlatformSessionLocal()
    try:
        return meta_privacy.handle_data_deletion(db, meta_user_id, lambda tid: tenant_session(db, tid))
    finally:
        db.close()


@router.post("/api/meta/deauthorize", include_in_schema=False)
async def deauthorize(request: Request):
    user_id = _verified_user_id(await request.body(), "deauthorize", request.headers.get("content-type"))
    try:
        result = await run_in_threadpool(_deauthorize, user_id)
    except (SQLAlchemyError, HTTPException):
        logger.exception("meta_deauth_erro")
        raise HTTPException(status_code=500, detail="Temporary failure") from None
    logger.info("meta_deauth meta_user_id=%s canais=%d revogados=%d", user_id, result["channels"], result["revoked"])
    return {"received": True}


@router.post("/api/meta/data-deletion", include_in_schema=False)
async def data_deletion(request: Request):
    user_id = _verified_user_id(await request.body(), "data-deletion", request.headers.get("content-type"))
    try:
        result = await run_in_threadpool(_delete_data, user_id)
    except (SQLAlchemyError, HTTPException):
        logger.exception("meta_exclusao_erro")
        raise HTTPException(status_code=500, detail="Temporary failure") from None
    logger.info("meta_exclusao meta_user_id=%s canais=%d excluidos=%d", user_id, result["channels"], result["deleted"])
    base = settings.omni_public_base_url.rstrip("/")
    return {"url": f"{base}/omni/data-deletion-status?code={result['code']}", "confirmation_code": result["code"]}


# --------------------------------------------------------------------------- pagina publica de status
_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>Data deletion status</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f4f6fa;color:#10203a}}
main{{max-width:640px;margin:48px auto;padding:0 20px}}
.card{{background:#fff;border-radius:14px;padding:28px;box-shadow:0 2px 12px rgba(16,32,58,.08)}}
h1{{font-size:1.35rem;margin:0 0 4px}} h2{{font-size:1rem;margin:22px 0 4px;color:#44546f}}
.code{{font-family:ui-monospace,Menlo,Consolas,monospace;background:#eef2f9;border-radius:6px;padding:2px 8px}}
.s{{display:inline-block;border-radius:999px;padding:3px 12px;font-size:.85rem;font-weight:600;background:{bg};color:{fg}}}
footer{{margin-top:18px;font-size:.85rem;color:#44546f}} a{{color:#1a56db}}
</style></head><body><main><div class="card">
<h1>Data deletion status · Status da exclusão de dados</h1>
<p>Code · Código: <span class="code">{code}</span></p>
<p><span class="s">{badge}</span></p>
<h2>English</h2><p>{en}</p>
<h2>Português</h2><p>{pt}</p>
</div>
<footer><a href="{site}/privacy-policy-en.html">Privacy Policy</a> · <a href="{site}/politica-de-privacidade.html">Política de Privacidade</a> · MDP Consultoria</footer>
</main></body></html>"""

_TEXT = {
    "RECEBIDO": ("Received", "#fff4d6", "#7a5200",
                 "Your request was received and the deletion is in progress.",
                 "Seu pedido foi recebido e a exclusão está em andamento."),
    "CONCLUIDO": ("Completed", "#dff7e6", "#14653a",
                  "The data linked to this request (connection, conversations, messages and comments) was deleted on {when}.",
                  "Os dados ligados a este pedido (conexão, conversas, mensagens e comentários) foram excluídos em {when}."),
    "SEM_CORRESPONDENCIA": ("Nothing to delete", "#e6eefc", "#1a3f8f",
                            "Your request was received. We found no data linked to this account, so there was nothing to delete.",
                            "Seu pedido foi recebido. Não encontramos dados ligados a esta conta, então não havia o que excluir."),
}


def _render(code: str, status: str, when: str, http_status: int = 200) -> HTMLResponse:
    badge, bg, fg, en, pt = _TEXT[status]
    body = _PAGE.format(code=html.escape(code), badge=html.escape(badge), bg=bg, fg=fg, site=SITE,
                        en=html.escape(en.format(when=when)), pt=html.escape(pt.format(when=when)))
    return HTMLResponse(body, status_code=http_status, headers={"Cache-Control": "no-store"})


def _not_found(code: str) -> HTMLResponse:
    body = _PAGE.format(code=html.escape((code or "")[:40]), badge="Not found", bg="#fde8e8", fg="#8f1d1d", site=SITE,
                        en="We could not find a deletion request with this code.",
                        pt="Não encontramos um pedido de exclusão com este código.")
    return HTMLResponse(body, status_code=404, headers={"Cache-Control": "no-store"})


@router.get("/omni/data-deletion-status", include_in_schema=False)
def data_deletion_status(code: str = Query(default="", max_length=64)):
    db = PlatformSessionLocal()
    try:
        row = meta_privacy.get_request_status(db, code)
    finally:
        db.close()
    if not row or row["tipo"] != "EXCLUSAO":
        return _not_found(code)
    done = row["concluido_em"]
    when = done.strftime("%Y-%m-%d %H:%M UTC") if done else ""
    return _render(code, row["status"], when)
