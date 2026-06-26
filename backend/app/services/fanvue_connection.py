"""Fanvue connection helpers: access token refresh, webhook signing secret."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.connectors.fanvue.oauth import FanvueOAuthError, refresh_fanvue_access_token
from app.db.models import FanvueConnection
from app.services.crypto_secret import decrypt_secret, encrypt_secret

log = logging.getLogger(__name__)

_TOKEN_REFRESH_SKEW_SECONDS = 120


def fanvue_platform_webhook_signing_secret() -> str:
    return (
        (settings.fanvue_webhook_signing_secret or settings.fanvue_webhook_secret or "").strip()
    )


def fanvue_platform_webhook_url() -> str | None:
    if not fanvue_platform_webhook_signing_secret():
        return None
    base = (settings.public_app_url or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/api/webhooks/fanvue"


def resolve_fanvue_webhook_signing_secret(conn: FanvueConnection | None) -> str:
    platform = fanvue_platform_webhook_signing_secret()
    if platform:
        return platform
    if conn and (conn.webhook_signing_secret_encrypted or "").strip():
        return decrypt_secret(conn.webhook_signing_secret_encrypted)
    raise ValueError("Fanvue webhook signing secret is not configured")


def _token_expired(conn: FanvueConnection) -> bool:
    if not conn.token_expires_at:
        return False
    now = datetime.now(timezone.utc)
    exp = conn.token_expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return now >= exp - timedelta(seconds=_TOKEN_REFRESH_SKEW_SECONDS)


async def ensure_fanvue_access_token(
    session: AsyncSession,
    conn: FanvueConnection,
) -> str:
    if not _token_expired(conn):
        return decrypt_secret(conn.access_token_encrypted)

    refresh_raw = ""
    if conn.refresh_token_encrypted:
        refresh_raw = decrypt_secret(conn.refresh_token_encrypted)
    if not refresh_raw:
        return decrypt_secret(conn.access_token_encrypted)

    try:
        payload = await refresh_fanvue_access_token(refresh_token=refresh_raw)
    except FanvueOAuthError as e:
        log.warning("fanvue token refresh failed user=%s: %s", conn.user_id, e)
        return decrypt_secret(conn.access_token_encrypted)

    access = str(payload.get("access_token") or "").strip()
    if not access:
        raise FanvueOAuthError("Fanvue refresh response missing access_token")

    conn.access_token_encrypted = encrypt_secret(access)
    refresh_new = str(payload.get("refresh_token") or "").strip()
    if refresh_new:
        conn.refresh_token_encrypted = encrypt_secret(refresh_new)
    expires_in = payload.get("expires_in")
    if expires_in is not None:
        try:
            sec = int(expires_in)
            conn.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=sec)
        except (TypeError, ValueError):
            pass
    await session.commit()
    return access
