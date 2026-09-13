"""Резолв PeerUser для исходящих — StringSession не хранит entity cache между connect."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.tl.types import InputPeerUser, PeerUser

from app.db.models import Message, MessageDirection

log = logging.getLogger(__name__)


async def resolve_telegram_user_peer(
    client: TelegramClient,
    user_id: int,
    *,
    username: str | None = None,
    access_hash: int | None = None,
):
    """InputPeer для send_message — по access_hash, кэшу, @username или списку диалогов."""
    if access_hash:
        try:
            return InputPeerUser(user_id, int(access_hash))
        except (TypeError, ValueError):
            pass

    try:
        return await client.get_input_entity(PeerUser(user_id))
    except (ValueError, TypeError):
        pass

    uname = (username or "").strip().lstrip("@")
    if uname:
        try:
            ent = await client.get_entity(uname)
            if int(getattr(ent, "id", 0) or 0) == user_id:
                return await client.get_input_entity(ent)
        except Exception as exc:
            log.debug("telegram_user resolve by @%s failed: %s", uname, exc)

    for archived in (False, True):
        async for dialog in client.iter_dialogs(archived=archived):
            ent = dialog.entity
            if int(getattr(ent, "id", 0) or 0) == user_id:
                return await client.get_input_entity(ent)

    raise ValueError(
        f"Could not find the input entity for PeerUser(user_id={user_id}) (PeerUser). "
        "Please read https://docs.telethon.dev/en/stable/concepts/entities.html to find out more details."
    )


async def load_telegram_user_peer_hints(
    session: AsyncSession,
    conv_id: int,
    user_display_name: str | None,
) -> tuple[str | None, int | None]:
    """@username и access_hash из последнего входящего (meta.from_user_access_hash)."""
    username: str | None = None
    name = (user_display_name or "").strip()
    if name.startswith("@"):
        username = name[1:].strip() or None

    access_hash: int | None = None
    meta_raw = await session.scalar(
        select(Message.meta)
        .where(
            Message.conversation_id == conv_id,
            Message.direction == MessageDirection.inbound,
        )
        .order_by(Message.id.desc())
        .limit(1)
    )
    if meta_raw:
        try:
            data = json.loads(meta_raw)
            if isinstance(data, dict) and data.get("from_user_access_hash") is not None:
                access_hash = int(data["from_user_access_hash"])
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    return username, access_hash
