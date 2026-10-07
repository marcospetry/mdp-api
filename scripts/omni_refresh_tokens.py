"""Renova os tokens longos (60 dias) das contas do Instagram conectadas ao Omni.

Agendar UMA vez por dia no Dokploy (mdp-api > Schedules), comando:  python scripts/omni_refresh_tokens.py
Imprime so contagens, nunca tokens. Nao faz nada se OMNI_META_ENABLED estiver desligado.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.database import PlatformSessionLocal
from app.services import meta_crypto, meta_instagram, omni_connections

EXPIRED_CODES = {"190", "102"}  # token invalido ou expirado


def run(now=None) -> dict:
    stats = {"vencendo": 0, "renovados": 0, "erros": 0, "expirados": 0}
    db = PlatformSessionLocal()
    try:
        for conn in omni_connections.due_for_refresh(db, now):
            stats["vencendo"] += 1
            try:
                res = meta_instagram.refresh_long_lived(meta_crypto.decrypt_token(conn["token_enc"]))
                omni_connections.mark_refreshed(db, conn["conexao_id"], res["access_token"], res["expires_in"])
                stats["renovados"] += 1
            except meta_instagram.MetaApiError as exc:
                expired = exc.code in EXPIRED_CODES
                omni_connections.mark_error(db, conn["conexao_id"], exc.code, expired)
                stats["erros"] += 1
                stats["expirados"] += int(expired)
            except RuntimeError:
                omni_connections.mark_error(db, conn["conexao_id"], "decrypt", False)
                stats["erros"] += 1
    finally:
        db.close()
    return stats


if __name__ == "__main__":
    if not settings.omni_meta_enabled:
        print("OMNI_META_ENABLED desligado: nada a fazer.")
        sys.exit(0)
    print(run())
