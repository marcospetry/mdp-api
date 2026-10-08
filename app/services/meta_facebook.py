"""Cliente do Facebook (Messenger + comentarios de Pagina) com Facebook Login for Business.

Fluxo (documentacao oficial da Meta, conferida em 08/10/2026):
  login            https://www.facebook.com/<versao>/dialog/oauth?config_id=...        (config de token de USUARIO)
  codigo -> token  GET  https://graph.facebook.com/<versao>/oauth/access_token
  token longo      GET  .../oauth/access_token?grant_type=fb_exchange_token           (usuario, ~60 dias)
  token da Pagina  GET  .../me/accounts  com o token longo do usuario -> token da Pagina SEM expiracao
  webhook          POST .../<page-id>/subscribed_apps?subscribed_fields=messages,feed  (token da Pagina)
  mensagem         POST .../<page-id>/messages        resposta ao comentario: POST .../<comment-id>/comments

Toda chamada HTTP passa por http_json() (o ponto que os testes substituem; reaproveita o de meta_instagram).
Tokens e codigos nunca vao para log.
"""
from __future__ import annotations

import logging
from urllib.parse import urlencode

from app.config import settings
from app.services import meta_instagram
from app.services.meta_instagram import MetaApiError, verify_signature  # noqa: F401 - reexportados

logger = logging.getLogger("mdp.meta.facebook")

GRAPH_HOST = "https://graph.facebook.com"
DIALOG = "https://www.facebook.com"
# as 6 permissoes de Pagina da fila do App Review (as mesmas da configuracao de login)
SCOPES = (
    "pages_show_list",
    "pages_manage_metadata",
    "pages_messaging",
    "pages_read_engagement",
    "pages_read_user_content",
    "pages_manage_engagement",
)
WEBHOOK_FIELDS = "messages,feed"
REQUIRED_TASKS = {"MESSAGING", "MODERATE"}  # tarefas da Pagina exigidas pela Meta para mensagens e comentarios


def http_json(*args, **kwargs) -> dict:
    return meta_instagram.http_json(*args, **kwargs)


def app_secret() -> str | None:
    for s in (settings.facebook_app_secret, settings.meta_whatsapp_app_secret):
        if s and s != "change-me":
            return s
    return None


def graph_url(path: str) -> str:
    return f"{GRAPH_HOST}/{settings.meta_graph_version}/{path.lstrip('/')}"


def build_authorize_url(redirect_uri: str, state: str) -> str:
    query = {
        "client_id": settings.facebook_app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "override_default_response_type": "true",
        "config_id": settings.facebook_login_config_id,
        "state": state,
    }
    return f"{DIALOG}/{settings.meta_graph_version}/dialog/oauth?{urlencode(query)}"


def exchange_code(code: str, redirect_uri: str) -> dict:
    body = http_json("GET", graph_url("oauth/access_token"), params={
        "client_id": settings.facebook_app_id, "client_secret": app_secret(), "redirect_uri": redirect_uri, "code": code})
    if not body.get("access_token"):
        raise MetaApiError(200, "no_token", "resposta sem access_token")
    return {"access_token": body["access_token"]}


def to_long_lived(user_token: str) -> dict:
    body = http_json("GET", graph_url("oauth/access_token"), params={
        "grant_type": "fb_exchange_token", "client_id": settings.facebook_app_id, "client_secret": app_secret(),
        "fb_exchange_token": user_token})
    if not body.get("access_token"):
        raise MetaApiError(200, "no_token", "resposta sem access_token")
    return {"access_token": body["access_token"]}


def get_me(user_token: str) -> dict:
    body = http_json("GET", graph_url("me"), params={"fields": "id,name", "access_token": user_token})
    if not body.get("id"):
        raise MetaApiError(200, "no_user_id", "resposta sem id")
    return {"id": str(body["id"]), "name": body.get("name")}


def granted_permissions(user_token: str) -> set[str]:
    body = http_json("GET", graph_url("me/permissions"), params={"access_token": user_token})
    return {str(p.get("permission")) for p in body.get("data", []) if isinstance(p, dict) and p.get("status") == "granted"}


def list_pages(user_token: str) -> list[dict]:
    """Paginas que o usuario autorizou, cada uma com o PROPRIO token (de longa duracao, sem expiracao quando o token do
    usuario e longo). Nunca logar o resultado."""
    body = http_json("GET", graph_url("me/accounts"), params={
        "fields": "id,name,username,access_token,tasks", "limit": 25, "access_token": user_token})
    return [p for p in body.get("data", []) if isinstance(p, dict) and p.get("id") and p.get("access_token")]


def eligible_pages(pages: list[dict]) -> list[dict]:
    """So as Paginas em que o usuario tem as tarefas de mensagens e de moderacao. Sem o campo 'tasks' a Pagina e aceita."""
    out = []
    for p in pages:
        tasks = p.get("tasks")
        if tasks is None or REQUIRED_TASKS <= {str(t).upper() for t in tasks}:
            out.append(p)
    return out


def subscribe_webhooks(page_token: str, page_id: str, fields: str = WEBHOOK_FIELDS) -> dict:
    return http_json("POST", graph_url(f"{page_id}/subscribed_apps"), params={"subscribed_fields": fields, "access_token": page_token})


def send_text(page_token: str, page_id: str, psid: str, text: str) -> dict:
    return http_json("POST", graph_url(f"{page_id}/messages"), headers={"Authorization": f"Bearer {page_token}"},
                     json_body={"messaging_type": "RESPONSE", "recipient": {"id": psid}, "message": {"text": text}})


def reply_comment(page_token: str, comment_id: str, message: str) -> dict:
    return http_json("POST", graph_url(f"{comment_id}/comments"), headers={"Authorization": f"Bearer {page_token}"},
                     json_body={"message": message})


def get_user_profile(page_token: str, psid: str) -> dict:
    return http_json("GET", graph_url(psid), params={"fields": "name", "access_token": page_token}, timeout=5.0)


def get_post(page_token: str, post_id: str) -> dict:
    return http_json("GET", graph_url(post_id), params={"fields": "id,message,permalink_url", "access_token": page_token}, timeout=5.0)


def list_posts(page_token: str, page_id: str, limit: int = 8) -> list[dict]:
    body = http_json("GET", graph_url(f"{page_id}/posts"), params={"fields": "id,message,permalink_url,created_time", "limit": limit,
                                                                  "access_token": page_token})
    return [p for p in body.get("data", []) if isinstance(p, dict)]


def list_comments(page_token: str, post_id: str, limit: int = 30) -> list[dict]:
    body = http_json("GET", graph_url(f"{post_id}/comments"), params={
        "fields": "id,message,from,created_time,parent{id}", "filter": "stream", "limit": limit, "access_token": page_token})
    return [c for c in body.get("data", []) if isinstance(c, dict)]
