"""Доставка медиа из медиатеки после текстового ответа companion bot."""

from __future__ import annotations

import asyncio
import logging
import random

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CompanionMediaAsset, Conversation, Message, MessageAttachmentKind
from app.services.chat_messages import add_message_attachment
from app.services.chat_attachment import save_chat_media_bytes
from app.services.companion_bot.media_planner import MediaAction, MediaPlan, parse_media_plan_from_snapshot
from app.services.companion_bot.send import broadcast_companion_message, send_companion_outbound
from app.services.companion_media.library import mark_media_sent
from app.services.companion_media.storage import resolve_companion_media_file

log = logging.getLogger(__name__)

_SEND_ACTIONS: frozenset[MediaAction] = frozenset(
    {"send_free", "send_teaser", "send_paid_unlocked"}
)


async def _load_asset_row(
    session: AsyncSession,
    *,
    owner_id: int,
    asset_id: int,
) -> CompanionMediaAsset | None:
    row = await session.get(CompanionMediaAsset, asset_id)
    if not row or row.user_id != owner_id or row.status != "active":
        return None
    return row


async def deliver_companion_media_plan(
    session: AsyncSession,
    *,
    owner_id: int,
    conv: Conversation,
    plan: MediaPlan,
    bot_response_event_id: int,
    reply_to_message_id: int | None = None,
    sender_user_id: int | None = None,
    donation_unlock_event_id: int | None = None,
) -> list[Message]:
    """
    Отправляет 1..N файлов отдельными сообщениями после текста.
    Каждый файл — отдельное outbound + запись в CompanionMediaSendLog.
    """
    if plan.action not in _SEND_ACTIONS or not plan.asset_ids:
        return []

    sent_rows: list[Message] = []
    for idx, asset_id in enumerate(plan.asset_ids):
        asset = await _load_asset_row(session, owner_id=owner_id, asset_id=asset_id)
        if not asset:
            log.info(
                "companion media skip missing asset conv=%s asset=%s",
                conv.id,
                asset_id,
            )
            continue

        path = resolve_companion_media_file(owner_id, asset.relative_path)
        if not path:
            log.warning(
                "companion media file missing conv=%s asset=%s path=%s",
                conv.id,
                asset_id,
                asset.relative_path,
            )
            continue

        raw = path.read_bytes()
        mime = (asset.content_type or "image/jpeg").strip()
        is_video = (asset.media_type or "").lower() == "video" or mime.startswith("video/")

        image_bytes: bytes | None = None
        image_mime: str | None = None
        video_bytes: bytes | None = None
        video_mime: str | None = None
        if is_video:
            video_bytes = raw
            video_mime = mime
        else:
            image_bytes = raw
            image_mime = mime

        # Короткая подпись только к первому кадру серии — как живой чат.
        caption = ""
        if idx == 0 and plan.action == "send_paid_unlocked":
            caption = "😏"
        elif idx == 0 and plan.action == "send_teaser":
            caption = random.choice(["", "😉", "like this?", "чуть-чуть 😏", ""])

        # Первое медиа можно привязать к reply; остальные — цепочкой без reply.
        reply_id = reply_to_message_id if idx == 0 else None

        row = await send_companion_outbound(
            session,
            owner_id=owner_id,
            conv=conv,
            text=caption,
            reply_to_message_id=reply_id,
            bot_response_event_id=bot_response_event_id,
            sender_user_id=sender_user_id,
            image_bytes=image_bytes,
            image_mime=image_mime,
            video_bytes=video_bytes,
            video_mime=video_mime,
            companion_media_asset_id=asset.id,
            donation_unlock_event_id=donation_unlock_event_id,
        )

        # Копия в chat_media для UI кабинета.
        try:
            rel, stored_mime = save_chat_media_bytes(
                owner_id=owner_id,
                raw=raw,
                content_type=mime,
            )
            await add_message_attachment(
                session,
                message_id=row.id,
                relative_path=rel,
                mime_type=stored_mime,
                kind=MessageAttachmentKind.image,
            )
        except Exception as e:
            log.warning("companion media attachment save failed msg=%s: %s", row.id, e)

        await mark_media_sent(
            session,
            owner_id=owner_id,
            conversation_id=conv.id,
            asset_ids=[asset.id],
            message_id=row.id,
        )
        sent_rows.append(row)

        if idx + 1 < len(plan.asset_ids):
            await asyncio.sleep(random.uniform(0.6, 1.4))

    return sent_rows


async def deliver_companion_media_from_snapshot(
    session: AsyncSession,
    *,
    owner_id: int,
    conv: Conversation,
    state_snapshot: dict,
    bot_response_event_id: int,
    reply_to_message_id: int | None = None,
    sender_user_id: int | None = None,
    donation_unlock_event_id: int | None = None,
) -> list[Message]:
    plan = parse_media_plan_from_snapshot(state_snapshot)
    return await deliver_companion_media_plan(
        session,
        owner_id=owner_id,
        conv=conv,
        plan=plan,
        bot_response_event_id=bot_response_event_id,
        reply_to_message_id=reply_to_message_id,
        sender_user_id=sender_user_id,
        donation_unlock_event_id=donation_unlock_event_id,
    )
