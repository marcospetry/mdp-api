"""Cliente da Instagram API com Instagram Login (Business Login for Instagram).

Endpoints conforme a documentacao oficial da Meta (conferida em 07/10/2026):
  autorizacao      https://www.instagram.com/oauth/authorize
  codigo -> token  POST https://api.instagram.com/oauth/access_token
  token longo      GET  https://graph.instagram.com/access_token?grant_type=ig_exchange_token
  renovar token    GET  https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token
  demais chamadas  https://graph.instagram.com/<versao>/...

TODA chamada HTTP passa por http_json(): e o unico ponto que os testes substituem. Tokens e codigos nunca vao para log.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger("mdp.meta.instagram")

GRAPH_HOST = "https://graph.instagram.com"
OAUTH_AUTHORIZE = "https://www.instagram.com/oauth/authorize"
OAUTH_TOKEN = "https://api.instagram.com/oauth/access_token"
SCOPES = (
    "instagram_business_basic",
    "instagram_business_manage_messages",
    "instagram_business_manage_comments",
)
WEBHOOK_FIELDS = "messages,comments"
PROFESSIONAL_TYPES = {"business", "media_creator", "creator"}


class MetaApiError(Exception):
    """Erro devolvido pela Meta (ou de rede). `code` e texto curto e seguro para guardar e mostrar."""

    def __init__(self, status: int, code: str, message: str = ""):
        super().__init__(f"{status} {code}")
        self.status, self.code, self.message = status, str(code), message


def graph_url(path: str) -> str:
    return f"{GRAPH_HOST}/{settings.meta_graph_version}/{path.lstrip('/')}"


def http_json(method: str, url: str, *, params: dict | None = None, data: dict | None = None,
              json_body: Any = None, headers: dict | None = None, timeout: float = 15.0) -> dict:
    try:
        resp = httpx.request(method, url, params=params, data=data, json=json_body, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise MetaApiError(0, "network", exc.__class__.__name__) from None
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code >= 400 or (isinstance(body, dict) and "error" in body) or (isinstance(body, dict) and "error_type" in body):
        err = body.get("error") if isinstance(body, dict) and isinstance(body.get("error"), dict) else body
        code = (err or {}).get("code") or resp.status_code
        msg = (err or {}).get("message") or (err or {}).get("error_message") or ""
        raise MetaApiError(resp.status_code, str(code), str(msg)[:200])
    return body if isinstance(body, dict) else {"data": body}


def _first(body: dict) -> dict:
    """A Meta responde ora com o objeto, ora com {"data": [objeto]}: aceita os dois."""
    data = body.get("data")
    if isinstance(data, list) and data:
        return data[0] if isinstance(data[0], dict) else {}
    return body


def build_authorize_url(redirect_uri: str, state: str) -> str:
    query = {
        "client_id": settings.instagram_app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(SCOPES),
        "state": state,
        "force_reauth": "true",
    }
    return f"{OAUTH_AUTHORIZE}?{urlencode(query)}"


def exchange_code(code: str, redirect_uri: str) -> dict:
    body = http_json("POST", OAUTH_TOKEN, data={
        "client_id": settings.instagram_app_id, "client_secret": settings.instagram_app_secret,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri, "code": code,
    })
    item = _first(body)
    if not item.get("access_token"):
        raise MetaApiError(200, "no_token", "resposta sem access_token")
    return {"access_token": item["access_token"], "user_id": str(item.get("user_id", "")), "permissions": str(item.get("permissions", ""))}


def to_long_lived(short_token: str) -> dict:
    body = http_json("GET", f"{GRAPH_HOST}/access_token", params={
        "grant_type": "ig_exchange_token", "client_secret": settings.instagram_app_secret, "access_token": short_token})
    if not body.get("access_token"):
        raise MetaApiError(200, "no_token", "resposta sem access_token")
    return {"access_token": body["access_token"], "expires_in": int(body.get("expires_in") or 5183944)}


def refresh_long_lived(token: str) -> dict:
    body = http_json("GET", f"{GRAPH_HOST}/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": token})
    if not body.get("access_token"):
        raise MetaApiError(200, "no_token", "resposta sem access_token")
    return {"access_token": body["access_token"], "expires_in": int(body.get("expires_in") or 5183944)}


def get_me(token: str) -> dict:
    body = http_json("GET", graph_url("me"), params={"fields": "user_id,username,name,account_type", "access_token": token})
    item = _first(body)
    # user_id = ID da conta profissional = o "id" que chega nos webhooks (conferido na documentacao)
    if not item.get("user_id"):
        raise MetaApiError(200, "no_user_id", "resposta sem user_id")
    return {"user_id": str(item["user_id"]), "username": item.get("username"), "name": item.get("name"),
            "account_type": str(item.get("account_type") or "")}


def subscribe_webhooks(token: str, ig_id: str, fields: str = WEBHOOK_FIELDS) -> dict:
    return http_json("POST", graph_url(f"{ig_id}/subscribed_apps"), params={"subscribed_fields": fields, "access_token": token})


def send_text(token: str, ig_id: str, igsid: str, text: str) -> dict:
    return http_json("POST", graph_url(f"{ig_id}/messages"), headers={"Authorization": f"Bearer {token}"},
                     json_body={"recipient": {"id": igsid}, "message": {"text": text}})


def reply_comment(token: str, comment_id: str, message: str) -> dict:
    return http_json("POST", graph_url(f"{comment_id}/replies"), headers={"Authorization": f"Bearer {token}"},
                     json_body={"message": message})


def get_user_profile(token: str, igsid: str) -> dict:
    return http_json("GET", graph_url(igsid), params={"fields": "name,username", "access_token": token}, timeout=5.0)


def get_media(token: str, media_id: str) -> dict:
    return http_json("GET", graph_url(media_id), params={"fields": "id,caption,permalink", "access_token": token}, timeout=5.0)


def list_media(token: str, ig_id: str, limit: int = 8) -> list[dict]:
    body = http_json("GET", graph_url(f"{ig_id}/media"), params={"fields": "id,caption,permalink,timestamp", "limit": limit, "access_token": token})
    return [m for m in body.get("data", []) if isinstance(m, dict)]


def list_comments(token: str, media_id: str, limit: int = 30) -> list[dict]:
    body = http_json("GET", graph_url(f"{media_id}/comments"), params={"fields": "id,text,username,timestamp", "limit": limit, "access_token": token})
    return [c for c in body.get("data", []) if isinstance(c, dict)]


def verify_signature(raw_body: bytes, header_value: str | None, secrets: list[str]) -> bool:
    """X-Hub-Signature-256 = 'sha256=' + HMAC-SHA256(corpo bruto, App Secret). Aceita qualquer um dos segredos informados."""
    if not header_value or not header_value.startswith("sha256="):
        return False
    received = header_value.split("=", 1)[1]
    for secret in secrets:
        if not secret:
            continue
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, received):
            return True
    return False
