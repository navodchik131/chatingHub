"""Импорт истории диалогов Fanvue через GET /chats и GET /chats/{uuid}/messages."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.connectors.fanvue.client import (
    FanvueAPIError,
    fanvue_api_data_list,
    fanvue_api_has_more,
    list_fanvue_chat_messages,
    list_fanvue_chats,
)
from app.connectors.fanvue.handlers import ingest_fanvue_message_from_api
from app.db.models import Conversation, FanvueConnection, Platform
from app.services.fanvue_connection import ensure_fanvue_access_token

log = logging.getLogger(__name__)


def _fanvue_chat_fan(chat: dict[str, Any]) -> tuple[str, str]:
    user = chat.get("user") or chat.get("fan") or {}
    if isinstance(user, str) and user.strip():
        u = user.strip()
        return u, u
    if not isinstance(user, dict):
        user = {}
    uuid = str(
        user.get("uuid")
        or chat.get("userUuid")
        or chat.get("fanUserUuid")
        or ""
    ).strip()
    display = (
        user.get("displayName")
        or user.get("handle")
        or user.get("username")
        or uuid
    )
    return uuid, str(display)


def _message_sort_key(msg: dict[str, Any]) -> tuple[int, str]:
    raw = msg.get("sentAt") or msg.get("createdAt") or msg.get("sent_at") or ""
    ts = str(raw).strip()
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp()), str(msg.get("uuid") or "")
        except ValueError:
            pass
    return 0, str(msg.get("uuid") or "")


async def sync_fanvue_chat_history(
    session: AsyncSession,
    *,
    conn: FanvueConnection,
    max_chats: int | None = None,
    max_messages_per_chat: int | None = None,
    fetch_media: bool = True,
    silent_imports: bool = True,
) -> dict[str, int | list[str]]:
    owner_user_id = conn.user_id
    creator_uuid = (conn.creator_uuid or "").strip()
    if not creator_uuid:
        raise ValueError("Fanvue creator_uuid is not set")

    max_chats = max_chats if max_chats is not None else settings.fanvue_sync_max_chats
    max_messages_per_chat = (
        max_messages_per_chat
        if max_messages_per_chat is not None
        else settings.fanvue_sync_max_messages_per_chat
    )

    access_token = await ensure_fanvue_access_token(session, conn)

    stats: dict[str, int | list[str]] = {
        "chats_processed": 0,
        "messages_imported": 0,
        "messages_skipped": 0,
        "messages_empty": 0,
        "errors": [],
    }
    errors: list[str] = stats["errors"]  # type: ignore[assignment]

    page_size = min(50, max(1, max_messages_per_chat))
    chat_page = 1
    chats_seen = 0

    while chats_seen < max_chats:
        try:
            chat_payload = await list_fanvue_chats(
                access_token, page=chat_page, size=page_size
            )
        except FanvueAPIError as e:
            errors.append(f"GET /chats page={chat_page}: {e.status}")
            break

        chats = fanvue_api_data_list(chat_payload)
        if not chats:
            break

        for chat in chats:
            if chats_seen >= max_chats:
                break
            if not isinstance(chat, dict):
                continue
            fan_uuid, fan_display = _fanvue_chat_fan(chat)
            if not fan_uuid:
                continue
            chats_seen += 1

            msg_page = 1
            processed_in_chat = 0
            while processed_in_chat < max_messages_per_chat:
                try:
                    msg_payload = await list_fanvue_chat_messages(
                        access_token,
                        fan_uuid,
                        page=msg_page,
                        size=page_size,
                    )
                except FanvueAPIError as e:
                    from app.services.fanvue_peer_status import (
                        fanvue_api_body_indicates_invalid_user,
                        mark_conversation_peer_unavailable,
                    )

                    if fanvue_api_body_indicates_invalid_user(e.body):
                        conv = await session.scalar(
                            select(Conversation)
                            .where(
                                Conversation.user_id == owner_user_id,
                                Conversation.platform == Platform.fanvue,
                                Conversation.external_chat_id == fan_uuid,
                            )
                            .order_by(Conversation.updated_at.desc())
                            .limit(1)
                        )
                        if conv:
                            await mark_conversation_peer_unavailable(session, conv)
                    errors.append(
                        f"GET /chats/{fan_uuid}/messages page={msg_page}: {e.status}"
                    )
                    break

                messages = fanvue_api_data_list(msg_payload)
                if not messages:
                    break

                ordered = sorted(
                    (m for m in messages if isinstance(m, dict)),
                    key=_message_sort_key,
                )
                for msg in ordered:
                    if processed_in_chat >= max_messages_per_chat:
                        break
                    try:
                        result = await ingest_fanvue_message_from_api(
                            session,
                            owner_user_id=owner_user_id,
                            creator_uuid=creator_uuid,
                            fan_uuid=fan_uuid,
                            fan_display=fan_display,
                            msg=msg,
                            access_token=access_token,
                            fetch_media=fetch_media,
                            silent=silent_imports,
                            conn=conn,
                        )
                    except Exception as e:
                        log.warning("fanvue sync message failed fan=%s: %s", fan_uuid, e)
                        errors.append(f"message {msg.get('uuid')}: {e}")
                        continue
                    if result == "imported":
                        stats["messages_imported"] += 1
                    elif result == "skipped":
                        stats["messages_skipped"] += 1
                    else:
                        stats["messages_empty"] += 1
                    processed_in_chat += 1

                if not fanvue_api_has_more(
                    msg_payload, page=msg_page, page_size=page_size, fetched=len(messages)
                ):
                    break
                msg_page += 1

        if not fanvue_api_has_more(
            chat_payload, page=chat_page, page_size=page_size, fetched=len(chats)
        ):
            break
        chat_page += 1

    stats["chats_processed"] = chats_seen
    await session.commit()
    return stats


async def poll_fanvue_inbox(session: AsyncSession, *, conn: FanvueConnection) -> dict[str, int | list[str]]:
    """Подтянуть свежие сообщения только по активным диалогам из БД."""
    owner_user_id = conn.user_id
    creator_uuid = (conn.creator_uuid or "").strip()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.fanvue_inbox_poll_active_days)
    limit = settings.fanvue_inbox_poll_max_chats
    max_messages = settings.fanvue_inbox_poll_max_messages_per_chat

    conn_filter = Conversation.fanvue_connection_id == conn.id
    if creator_uuid:
        legacy_filter = (
            Conversation.fanvue_connection_id.is_(None),
            Conversation.external_topic_id == creator_uuid,
        )
        where_conn = or_(conn_filter, *legacy_filter)
    else:
        where_conn = conn_filter

    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == owner_user_id,
            Conversation.platform == Platform.fanvue,
            Conversation.updated_at >= cutoff,
            where_conn,
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    convs = list((await session.scalars(stmt)).all())

    stats: dict[str, int | list[str]] = {
        "chats_processed": len(convs),
        "messages_imported": 0,
        "messages_skipped": 0,
        "messages_empty": 0,
        "errors": [],
    }
    if not convs:
        return stats

    for conv in convs:
        fan_uuid = (conv.external_chat_id or "").strip()
        if not fan_uuid:
            continue
        try:
            n = await sync_fanvue_single_chat_recent(
                session,
                conn=conn,
                fan_uuid=fan_uuid,
                fan_display=conv.user_display_name or fan_uuid,
                max_messages=max_messages,
            )
            stats["messages_imported"] = int(stats["messages_imported"]) + n
        except Exception as e:
            log.warning("fanvue active poll failed fan=%s: %s", fan_uuid[:8], e)
            errors: list[str] = stats["errors"]  # type: ignore[assignment]
            errors.append(f"fan={fan_uuid[:8]}: {e}")

    await session.commit()
    return stats


async def sync_fanvue_single_chat_recent(
    session: AsyncSession,
    *,
    conn: FanvueConnection,
    fan_uuid: str,
    fan_display: str = "",
    max_messages: int = 12,
) -> int:
    """Синхронизировать последние сообщения одного диалога; вернуть число новых."""
    from app.connectors.fanvue.client import FanvueAPIError, fanvue_api_data_list, list_fanvue_chat_messages

    owner_user_id = conn.user_id
    creator_uuid = (conn.creator_uuid or "").strip()
    if not creator_uuid or not fan_uuid.strip():
        return 0
    access_token = await ensure_fanvue_access_token(session, conn)
    imported = 0
    try:
        msg_payload = await list_fanvue_chat_messages(
            access_token, fan_uuid.strip(), page=1, size=min(50, max_messages)
        )
    except FanvueAPIError as e:
        from app.services.fanvue_peer_status import (
            fanvue_api_body_indicates_invalid_user,
            mark_conversation_peer_unavailable,
        )

        if fanvue_api_body_indicates_invalid_user(e.body):
            from sqlalchemy import select

            from app.db.models import Conversation, Platform

            conv = await session.scalar(
                select(Conversation)
                .where(
                    Conversation.user_id == owner_user_id,
                    Conversation.platform == Platform.fanvue,
                    Conversation.external_chat_id == fan_uuid.strip(),
                )
                .order_by(Conversation.updated_at.desc())
                .limit(1)
            )
            if conv:
                await mark_conversation_peer_unavailable(session, conv)
                await session.commit()
        log.warning("fanvue single chat sync failed fan=%s: %s", fan_uuid[:8], e.status)
        return 0
    messages = fanvue_api_data_list(msg_payload)
    ordered = sorted(
        (m for m in messages if isinstance(m, dict)),
        key=_message_sort_key,
    )
    for msg in ordered[-max_messages:]:
        try:
            result = await ingest_fanvue_message_from_api(
                session,
                owner_user_id=owner_user_id,
                creator_uuid=creator_uuid,
                fan_uuid=fan_uuid.strip(),
                fan_display=fan_display or fan_uuid,
                msg=msg,
                access_token=access_token,
                fetch_media=True,
                silent=False,
                conn=conn,
            )
        except Exception as e:
            log.warning("fanvue single chat message failed: %s", e)
            continue
        if result == "imported":
            imported += 1
    if imported:
        await session.commit()
    return imported
