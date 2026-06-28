"""Instagram connection helpers: token refresh."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.connectors.instagram.oauth import InstagramOAuthError, refresh_instagram_access_token
from app.db.models import InstagramConnection
from app.services.crypto_secret import decrypt_secret, encrypt_secret

log = logging.getLogger(__name__)

_TOKEN_REFRESH_SKEW_SECONDS = 3600


def instagram_platform_webhook_url() -> str | None:
    base = (settings.public_app_url or "").strip().rstrip("/")
    if not base or not base.lower().startswith("https://"):
        return None
    return f"{base}/api/webhooks/instagram"


def instagram_webhook_configured() -> bool:
    return bool(
        (settings.instagram_app_secret or "").strip()
        and (settings.instagram_webhook_verify_token or "").strip()
    )


def _token_expired(conn: InstagramConnection) -> bool:
    if not conn.token_expires_at:
        return False
    now = datetime.now(timezone.utc)
    exp = conn.token_expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return now >= exp - timedelta(seconds=_TOKEN_REFRESH_SKEW_SECONDS)


async def ensure_instagram_access_token(
    session: AsyncSession,
    conn: InstagramConnection,
) -> str:
    current = decrypt_secret(conn.access_token_encrypted)
    if not _token_expired(conn):
        return current

    try:
        payload = await refresh_instagram_access_token(current)
    except InstagramOAuthError as e:
        log.warning("instagram token refresh failed user=%s: %s", conn.user_id, e)
        return current

    access = str(payload.get("access_token") or "").strip()
    if not access:
        return current

    conn.access_token_encrypted = encrypt_secret(access)
    expires_in = payload.get("expires_in")
    if expires_in is not None:
        try:
            conn.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            pass
    await session.commit()
    return access
