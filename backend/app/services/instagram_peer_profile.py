"""Instagram IGSID → человекочитаемое имя (@username / name) и аватар."""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.instagram.client import fetch_instagram_user_profile
from app.db.models import Conversation, InstagramConnection, Platform
from app.services.instagram_connection import ensure_instagram_access_token

log = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"^Instagram(?:\s+[·•]\s*|\s+)(\d{5,})$")


def instagram_profile_avatar_url(profile: dict[str, Any] | None) -> str | None:
    url = str((profile or {}).get("profile_pic") or "").strip()
    return url if url.startswith("https://") else None


def format_instagram_peer_display(profile: dict[str, Any] | None, igsid: str) -> str:
    """@username > name > короткий fallback."""
    if profile:
        username = str(profile.get("username") or "").strip().lstrip("@")
        name = str(profile.get("name") or "").strip()
        if username:
            return f"@{username}"
        if name:
            return name
    sid = (igsid or "").strip()
    if sid:
        return f"Instagram · {sid[:12]}"
    return "Instagram"


def apply_instagram_peer_profile(
    conv: Conversation,
    profile: dict[str, Any] | None,
    igsid: str,
) -> str:
    """Обновляет display name и peer_avatar_url на диалоге."""
    display = format_instagram_peer_display(profile, igsid)
    conv.user_display_name = display
    avatar = instagram_profile_avatar_url(profile)
    if avatar:
        conv.peer_avatar_url = avatar
    return display


def instagram_peer_display_is_placeholder(display: str | None, igsid: str) -> bool:
    d = (display or "").strip()
    sid = (igsid or "").strip()
    if not d or not sid:
        return True
    if d == sid:
        return True
    if d == f"Instagram {sid[:10]}":
        return True
    if _PLACEHOLDER_RE.match(d):
        return True
    if d.startswith("Instagram ") and d[len("Instagram ") :].strip().isdigit():
        return True
    return False


async def resolve_instagram_peer_display(
    session: AsyncSession,
    conn: InstagramConnection,
    igsid: str,
    *,
    conv: Conversation | None = None,
) -> str:
    sid = (igsid or "").strip()
    if not sid:
        return "Instagram"
    try:
        token = await ensure_instagram_access_token(session, conn)
        profile = await fetch_instagram_user_profile(token, sid)
    except Exception as e:
        log.warning(
            "instagram peer profile lookup failed conn=%s igsid=%s: %s",
            conn.id,
            sid[:16],
            e,
        )
        profile = None
    display = format_instagram_peer_display(profile, sid)
    if conv is not None and profile:
        apply_instagram_peer_profile(conv, profile, sid)
    return display


async def refresh_instagram_conversation_display_names(
    session: AsyncSession,
    owner_id: int,
    convs: list[Conversation],
    *,
    limit: int = 8,
) -> int:
    """Подтягивает @username и аватар для старых диалогов с placeholder-именами."""
    pending = [
        c
        for c in convs
        if c.platform == Platform.instagram
        and (
            instagram_peer_display_is_placeholder(c.user_display_name, c.external_chat_id)
            or not (c.peer_avatar_url or "").strip()
        )
    ]
    if not pending:
        return 0

    conn_cache: dict[int, tuple[InstagramConnection, str] | None] = {}
    refreshed = 0

    for conv in pending[: max(1, limit)]:
        conn_id = conv.instagram_connection_id
        if not conn_id:
            continue
        if conn_id not in conn_cache:
            row = await session.get(InstagramConnection, conn_id)
            if not row or row.user_id != owner_id:
                conn_cache[conn_id] = None
            else:
                try:
                    tok = await ensure_instagram_access_token(session, row)
                    conn_cache[conn_id] = (row, tok)
                except Exception as e:
                    log.warning("instagram name refresh token conn=%s: %s", conn_id, e)
                    conn_cache[conn_id] = None

        cached = conn_cache.get(conn_id)
        if not cached:
            continue
        _conn, token = cached
        profile = await fetch_instagram_user_profile(token, conv.external_chat_id)
        if not profile:
            continue
        before_name = (conv.user_display_name or "").strip()
        before_avatar = (conv.peer_avatar_url or "").strip()
        display = apply_instagram_peer_profile(conv, profile, conv.external_chat_id)
        if (
            display != before_name
            or (conv.peer_avatar_url or "").strip() != before_avatar
        ):
            refreshed += 1

    if refreshed:
        await session.commit()
    return refreshed
