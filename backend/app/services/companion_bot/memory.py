"""Авто-обновление AI-заметок (профиль фана, контекст дня) перед ответом компаньона."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    Conversation,
    ConversationNote,
    ConversationNoteKind,
    Message,
    MessageDirection,
)
from app.services.conversation_notes import (
    extract_conversation_memory_from_transcript,
    format_messages_transcript_ru,
    upsert_ai_conversation_notes,
)
from app.services.studio_keys import StudioOpenAiCredentials

log = logging.getLogger(__name__)


async def _latest_ai_note_updated(
    session: AsyncSession, conv_id: int
) -> datetime | None:
    row = await session.scalar(
        select(func.max(ConversationNote.updated_at)).where(
            ConversationNote.conversation_id == conv_id,
            ConversationNote.kind.in_(
                [ConversationNoteKind.ai_profile, ConversationNoteKind.ai_daily]
            ),
        )
    )
    return row


async def _inbound_count_since(
    session: AsyncSession, conv_id: int, since: datetime | None
) -> int:
    q = select(func.count()).select_from(Message).where(
        Message.conversation_id == conv_id,
        Message.direction == MessageDirection.inbound,
    )
    if since is not None:
        q = q.where(Message.created_at > since)
    return int(await session.scalar(q) or 0)


async def maybe_refresh_companion_memory(
    session: AsyncSession,
    *,
    conv: Conversation,
    messages: list[Message],
    credentials: StudioOpenAiCredentials | None,
) -> bool:
    """
    Обновляет ai_profile / ai_daily, если заметки устарели или накопилось достаточно новых реплик фана.
    Возвращает True, если заметки были обновлены.
    """
    if not settings.companion_memory_auto_enabled:
        return False
    if not credentials or not (credentials.api_key or "").strip():
        return False

    transcript = format_messages_transcript_ru(messages, conv.user_display_name)
    if not transcript.strip():
        return False

    last_updated = await _latest_ai_note_updated(session, conv.id)
    max_age = timedelta(minutes=int(settings.companion_memory_daily_max_age_minutes))
    stale = last_updated is None or (
        datetime.now(timezone.utc) - last_updated.replace(tzinfo=timezone.utc)
        if last_updated.tzinfo is None
        else datetime.now(timezone.utc) - last_updated
    ) > max_age

    n_inbound_since = await _inbound_count_since(session, conv.id, last_updated)
    enough_new = n_inbound_since >= int(settings.companion_memory_refresh_every_n_inbound)

    profile_note = await session.scalar(
        select(ConversationNote).where(
            ConversationNote.conversation_id == conv.id,
            ConversationNote.kind == ConversationNoteKind.ai_profile,
        )
    )
    if profile_note is None:
        stale = True

    if not stale and not enough_new:
        return False

    try:
        data = await extract_conversation_memory_from_transcript(
            transcript[-12000:],
            credentials=credentials,
        )
    except Exception as e:
        log.warning("companion memory refresh failed conv=%s: %s", conv.id, e)
        return False

    profile = str(data.get("profile") or "").strip()
    today = str(data.get("today") or "").strip()
    insights_raw = data.get("insights")
    insights: list[str] = []
    if isinstance(insights_raw, list):
        insights = [str(x).strip() for x in insights_raw if str(x).strip()]

    if not profile and not today:
        return False

    await upsert_ai_conversation_notes(
        session,
        conv_id=conv.id,
        profile=profile or None,
        today=today or None,
        insights=insights or None,
    )
    log.info(
        "companion memory refreshed conv=%s inbound_since=%s",
        conv.id,
        n_inbound_since,
    )
    return True
