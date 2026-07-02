"""Заметки по диалогу: ручные операторов и AI-сводки."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import (
    Conversation,
    ConversationNote,
    ConversationNoteKind,
    Message,
    MessageDirection,
    User,
)
from app.db.repo import list_messages
from app.services.studio_openai import StudioOpenAiCredentials, _chat_completion_text

log = logging.getLogger(__name__)

_KIND_ORDER = {
    ConversationNoteKind.ai_profile: 0,
    ConversationNoteKind.manual: 1,
    ConversationNoteKind.ai_daily: 2,
    ConversationNoteKind.ai_insight: 3,
}


def _author_label(note: ConversationNote, viewer: User) -> str:
    if note.kind != ConversationNoteKind.manual:
        return "AI"
    if note.author_user_id is None:
        return "Команда"
    if note.author_user_id == viewer.id:
        return "Вы"
    if note.author and note.author.member_login:
        return note.author.member_login
    return "Команда"


def note_to_dict(note: ConversationNote, viewer: User) -> dict:
    return {
        "id": note.id,
        "kind": note.kind.value,
        "content": note.content,
        "is_pinned": bool(note.is_pinned),
        "author_user_id": note.author_user_id,
        "author_label": _author_label(note, viewer),
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def list_conversation_notes(
    session: AsyncSession,
    *,
    conv: Conversation,
    viewer: User,
    owner_id: int | None = None,
    auto_refresh: bool = False,
) -> list[dict]:
    if auto_refresh and owner_id is not None:
        refreshed = await maybe_refresh_ai_conversation_notes(
            session,
            conv=conv,
            owner_id=owner_id,
        )
        if refreshed:
            await session.commit()
    stmt = (
        select(ConversationNote)
        .where(ConversationNote.conversation_id == conv.id)
        .options(selectinload(ConversationNote.author))
        .order_by(ConversationNote.id.asc())
    )
    rows = list((await session.scalars(stmt)).all())
    rows.sort(
        key=lambda n: (
            0 if n.kind == ConversationNoteKind.ai_profile else 1,
            0 if n.is_pinned else 1,
            _KIND_ORDER.get(n.kind, 9),
            -(n.updated_at or n.created_at).timestamp(),
        )
    )
    return [note_to_dict(n, viewer) for n in rows]


async def create_manual_note(
    session: AsyncSession,
    *,
    conv: Conversation,
    author: User,
    content: str,
    is_pinned: bool = False,
) -> dict:
    text = content.strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty note")
    row = ConversationNote(
        conversation_id=conv.id,
        author_user_id=author.id,
        kind=ConversationNoteKind.manual,
        content=text,
        is_pinned=bool(is_pinned),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return note_to_dict(row, author)


async def update_manual_note(
    session: AsyncSession,
    *,
    conv: Conversation,
    note_id: int,
    actor: User,
    owner_id: int,
    content: str | None = None,
    is_pinned: bool | None = None,
) -> dict:
    row = await session.scalar(
        select(ConversationNote).where(
            ConversationNote.id == note_id,
            ConversationNote.conversation_id == conv.id,
        )
    )
    if not row or row.kind != ConversationNoteKind.manual:
        raise HTTPException(status_code=404, detail="note not found")
    if row.author_user_id != actor.id and actor.id != owner_id:
        raise HTTPException(status_code=403, detail="Нельзя редактировать чужую заметку")
    if content is not None:
        text = content.strip()
        if not text:
            raise HTTPException(status_code=400, detail="empty note")
        row.content = text
    if is_pinned is not None:
        row.is_pinned = bool(is_pinned)
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    return note_to_dict(row, actor)


async def delete_note(
    session: AsyncSession,
    *,
    conv: Conversation,
    note_id: int,
    actor: User,
    owner_id: int,
) -> None:
    row = await session.scalar(
        select(ConversationNote).where(
            ConversationNote.id == note_id,
            ConversationNote.conversation_id == conv.id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="note not found")
    if row.kind != ConversationNoteKind.manual:
        raise HTTPException(status_code=400, detail="AI-заметки нельзя удалить вручную")
    if row.author_user_id != actor.id and actor.id != owner_id:
        raise HTTPException(status_code=403, detail="Нельзя удалить чужую заметку")
    await session.delete(row)
    await session.commit()


def format_messages_transcript_ru(messages: list[Message], display_name: str | None) -> str:
    """Транскрипт для AI-анализа (русские подписи ролей)."""
    return _format_messages_for_ai(messages, display_name)


async def extract_conversation_memory_from_transcript(
    transcript: str,
    *,
    credentials=None,
) -> dict:
    """Извлекает profile / today / insights из текста переписки."""
    model = (settings.openai_studio_model or "").strip() or "gpt-4o-mini"
    system = (
        "Ты аналитик переписки creator ↔ fan. Ответь только JSON без markdown.\n"
        "Поля:\n"
        '- profile: string, markdown-список известного о фане (имя/ник, возраст если есть, '
        "локация, семья, интересы, важные факты из диалога). Только факты из переписки.\n"
        '- today: string, актуальный контекст диалога: о чём говорили в последних сообщениях, '
        "на чём остановились, что фан ждёт или просил (2-4 предложения). "
        "Если переписка давно не обновлялась — кратко напомни последний смысл общения.\n"
        '- open_threads: string[], незакрытые темы/вопросы фана (0-5).\n'
        '- insights: string[], подсказки чатеру как отвечать (0-3).\n'
        "Язык: русский."
    )
    user_msg = f"Переписка:\n\n{transcript}"
    raw = await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=1200,
        temperature=0.3,
        credentials=credentials,
        timeout_seconds=90.0,
    )
    try:
        data = json.loads((raw or "").strip())
    except json.JSONDecodeError:
        data = {"profile": (raw or "").strip(), "today": "", "insights": []}
    if not isinstance(data, dict):
        data = {"profile": str(raw), "today": "", "insights": []}
    return data


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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


async def _message_count_since(
    session: AsyncSession, conv_id: int, since: datetime | None
) -> int:
    q = select(func.count()).select_from(Message).where(
        Message.conversation_id == conv_id,
    )
    if since is not None:
        q = q.where(Message.created_at > since)
    return int(await session.scalar(q) or 0)


def _ai_notes_need_refresh(
    *,
    last_updated: datetime | None,
    has_profile: bool,
    activity_since: int,
    inbound_since: int,
) -> bool:
    if not has_profile:
        return True
    if inbound_since >= int(settings.companion_memory_refresh_every_n_inbound):
        return True
    if activity_since <= 0:
        return False

    now = datetime.now(timezone.utc)
    if last_updated is None:
        return True

    updated = _as_utc(last_updated)
    max_age = timedelta(minutes=int(settings.companion_memory_daily_max_age_minutes))
    age_stale = (now - updated) > max_age
    day_stale = updated.date() < now.date()
    return age_stale or day_stale


async def maybe_refresh_ai_conversation_notes(
    session: AsyncSession,
    *,
    conv: Conversation,
    owner_id: int,
    messages: list[Message] | None = None,
    credentials: StudioOpenAiCredentials | None = None,
) -> bool:
    """
    Обновляет ai_profile / ai_daily, если заметки устарели или в диалоге появились новые сообщения.
    Возвращает True, если заметки были обновлены (commit — на вызывающей стороне).
    """
    if credentials is None:
        key = (settings.openai_api_key or "").strip()
        if not key:
            return False
        base = (settings.openai_base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
        org = (settings.openai_organization or "").strip()
        credentials = StudioOpenAiCredentials(api_key=key, base_url=base, organization=org)
    elif not (credentials.api_key or "").strip():
        return False

    if messages is None:
        messages = await list_messages(session, conv.id, owner_id, limit=80)

    transcript = format_messages_transcript_ru(messages, conv.user_display_name)
    if not transcript.strip():
        return False

    last_updated = await _latest_ai_note_updated(session, conv.id)
    profile_note = await session.scalar(
        select(ConversationNote).where(
            ConversationNote.conversation_id == conv.id,
            ConversationNote.kind == ConversationNoteKind.ai_profile,
        )
    )
    activity_since = await _message_count_since(session, conv.id, last_updated)
    inbound_since = await _inbound_count_since(session, conv.id, last_updated)

    if not _ai_notes_need_refresh(
        last_updated=last_updated,
        has_profile=profile_note is not None,
        activity_since=activity_since,
        inbound_since=inbound_since,
    ):
        return False

    try:
        data = await extract_conversation_memory_from_transcript(
            transcript[-12000:],
            credentials=credentials,
        )
    except Exception as e:
        log.warning("conversation notes auto-refresh failed conv=%s: %s", conv.id, e)
        return False

    profile = str(data.get("profile") or "").strip()
    today = str(data.get("today") or "").strip()
    insights_raw = data.get("insights")
    open_threads = data.get("open_threads")
    insights: list[str] = []
    if isinstance(insights_raw, list):
        insights = [str(x).strip() for x in insights_raw if str(x).strip()]
    if isinstance(open_threads, list):
        for t in open_threads[:5]:
            s = str(t).strip()
            if s:
                insights.append(f"Open thread: {s}")

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
        "conversation notes auto-refreshed conv=%s activity_since=%s inbound_since=%s",
        conv.id,
        activity_since,
        inbound_since,
    )
    return True


async def upsert_ai_conversation_notes(
    session: AsyncSession,
    *,
    conv_id: int,
    profile: str | None,
    today: str | None,
    insights: list[str] | None = None,
) -> None:
    if profile:
        await _upsert_ai_note(
            session,
            conv_id=conv_id,
            kind=ConversationNoteKind.ai_profile,
            content=profile.strip(),
            pinned=True,
        )
    if today:
        await _upsert_ai_note(
            session,
            conv_id=conv_id,
            kind=ConversationNoteKind.ai_daily,
            content=today.strip(),
            pinned=True,
        )
    if insights:
        await session.execute(
            delete(ConversationNote).where(
                ConversationNote.conversation_id == conv_id,
                ConversationNote.kind == ConversationNoteKind.ai_insight,
            )
        )
        now = datetime.now(timezone.utc)
        for item in insights[:5]:
            session.add(
                ConversationNote(
                    conversation_id=conv_id,
                    author_user_id=None,
                    kind=ConversationNoteKind.ai_insight,
                    content=item,
                    is_pinned=False,
                    created_at=now,
                    updated_at=now,
                )
            )


def _format_messages_for_ai(messages: list[Message], display_name: str | None) -> str:
    lines: list[str] = []
    if display_name:
        lines.append(f"Собеседник: {display_name}")
    for m in messages:
        who = "Фан" if m.direction == MessageDirection.inbound else "Модель"
        text = (m.text_original or m.text_translated or "").strip()
        if not text:
            continue
        lines.append(f"{who}: {text}")
    return "\n".join(lines)


async def _upsert_ai_note(
    session: AsyncSession,
    *,
    conv_id: int,
    kind: ConversationNoteKind,
    content: str,
    pinned: bool,
) -> None:
    existing = await session.scalar(
        select(ConversationNote).where(
            ConversationNote.conversation_id == conv_id,
            ConversationNote.kind == kind,
        )
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.content = content
        existing.is_pinned = pinned
        existing.updated_at = now
        return
    session.add(
        ConversationNote(
            conversation_id=conv_id,
            author_user_id=None,
            kind=kind,
            content=content,
            is_pinned=pinned,
            created_at=now,
            updated_at=now,
        )
    )


async def analyze_conversation_notes(
    session: AsyncSession,
    *,
    conv: Conversation,
    viewer: User,
    owner_id: int,
) -> list[dict]:
    if not (settings.openai_api_key or "").strip():
        raise HTTPException(
            status_code=503,
            detail="AI-анализ недоступен: на сервере не настроен OPENAI_API_KEY",
        )
    messages = await list_messages(session, conv.id, owner_id, limit=80)
    transcript = format_messages_transcript_ru(messages, conv.user_display_name)
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="Нет текста сообщений для анализа")

    try:
        data = await extract_conversation_memory_from_transcript(transcript[-12000:])
    except Exception as e:
        log.warning("conversation notes AI failed conv=%s: %s", conv.id, e)
        raise HTTPException(status_code=502, detail="AI-анализ не удался") from e

    profile = str(data.get("profile") or "").strip()
    today = str(data.get("today") or "").strip()
    insights_raw = data.get("insights")
    open_threads = data.get("open_threads")
    insights: list[str] = []
    if isinstance(insights_raw, list):
        insights = [str(x).strip() for x in insights_raw if str(x).strip()]
    if isinstance(open_threads, list):
        for t in open_threads[:5]:
            s = str(t).strip()
            if s:
                insights.append(f"Open thread: {s}")

    await upsert_ai_conversation_notes(
        session,
        conv_id=conv.id,
        profile=profile or None,
        today=today or None,
        insights=insights or None,
    )

    await session.commit()
    return await list_conversation_notes(session, conv=conv, viewer=viewer)
