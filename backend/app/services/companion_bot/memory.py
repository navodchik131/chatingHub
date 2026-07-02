"""Авто-обновление AI-заметок (профиль фана, контекст дня) перед ответом компаньона."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Conversation, Message
from app.services.conversation_notes import (
    format_messages_transcript_ru,
    maybe_refresh_ai_conversation_notes,
)
from app.services.studio_keys import StudioOpenAiCredentials

log = logging.getLogger(__name__)


async def maybe_refresh_companion_memory(
    session: AsyncSession,
    *,
    conv: Conversation,
    messages: list[Message],
    credentials: StudioOpenAiCredentials | None,
    owner_id: int,
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

    return await maybe_refresh_ai_conversation_notes(
        session,
        conv=conv,
        owner_id=owner_id,
        messages=messages,
        credentials=credentials,
    )
