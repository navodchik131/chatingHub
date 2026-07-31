"""Telethon-клиент из зашифрованной StringSession."""

from __future__ import annotations

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.config import settings
from app.connectors.telegram_user.proxy import telethon_proxy_tuple
from app.services.crypto_secret import decrypt_secret


def require_mtproto_config() -> tuple[int, str]:
    api_id = int(settings.telegram_api_id or 0)
    api_hash = (settings.telegram_api_hash or "").strip()
    if not api_id or not api_hash:
        raise RuntimeError(
            "MTProto не настроен: задайте TELEGRAM_API_ID и TELEGRAM_API_HASH (my.telegram.org)."
        )
    return api_id, api_hash


def build_telegram_client(*, session_encrypted: str | None = None) -> TelegramClient:
    api_id, api_hash = require_mtproto_config()
    session_str = ""
    if session_encrypted:
        session_str = decrypt_secret(session_encrypted)
    proxy = telethon_proxy_tuple()
    return TelegramClient(
        StringSession(session_str),
        api_id,
        api_hash,
        proxy=proxy,
        connection_retries=5,
        retry_delay=2,
    )
