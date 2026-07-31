"""Парсинг TELEGRAM_PROXY для Telethon."""

from __future__ import annotations

from urllib.parse import urlparse

from app.config import settings


def telethon_proxy_tuple() -> tuple | None:
    raw = (settings.telegram_proxy or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"socks5://{raw}"
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "socks5").lower()
    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        return None
    return (scheme, host, port)
