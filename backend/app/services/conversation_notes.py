"""Заметки по диалогу: ручные операторов и AI-сводки."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
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
from app.services.studio_openai import _chat_completion_text

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
) -> list[dict]:
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
    transcript = _format_messages_for_ai(messages, conv.user_display_name)
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="Нет текста сообщений для анализа")

    model = (settings.openai_studio_model or "").strip() or "gpt-4o-mini"
    system = (
        "Ты аналитик переписки creator ↔ fan. Ответь только JSON без markdown.\n"
        "Поля:\n"
        '- profile: string, markdown-список известного о фане (имя/ник, возраст если есть, '
        "локация, интересы, стиль, предпочтения). Только факты из переписки, без выдумок.\n"
        '- today: string, кратко о чём говорили в последних сообщениях (1-3 предложения).\n'
        '- insights: string[], дополнительные наблюдения для оператора (0-5 пунктов).\n"
        "Язык: русский."
    )
    user_msg = f"Переписка:\n\n{transcript[-12000:]}"
    try:
        raw = await _chat_completion_text(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1200,
            temperature=0.3,
            timeout_seconds=90.0,
        )
    except Exception as e:
        log.warning("conversation notes AI failed conv=%s: %s", conv.id, e)
        raise HTTPException(status_code=502, detail="AI-анализ не удался") from e

    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        data = {"profile": raw.strip(), "today": "", "insights": []}
    if not isinstance(data, dict):
        data = {"profile": str(raw), "today": "", "insights": []}

    profile = str(data.get("profile") or "").strip()
    today = str(data.get("today") or "").strip()
    insights_raw = data.get("insights")
    insights: list[str] = []
    if isinstance(insights_raw, list):
        insights = [str(x).strip() for x in insights_raw if str(x).strip()]

    if profile:
        await _upsert_ai_note(
            session,
            conv_id=conv.id,
            kind=ConversationNoteKind.ai_profile,
            content=profile,
            pinned=True,
        )
    if today:
        await _upsert_ai_note(
            session,
            conv_id=conv.id,
            kind=ConversationNoteKind.ai_daily,
            content=today,
            pinned=True,
        )
    if insights:
        await session.execute(
            delete(ConversationNote).where(
                ConversationNote.conversation_id == conv.id,
                ConversationNote.kind == ConversationNoteKind.ai_insight,
            )
        )
        now = datetime.now(timezone.utc)
        for item in insights[:5]:
            session.add(
                ConversationNote(
                    conversation_id=conv.id,
                    author_user_id=None,
                    kind=ConversationNoteKind.ai_insight,
                    content=item,
                    is_pinned=False,
                    created_at=now,
                    updated_at=now,
                )
            )

    await session.commit()
    return await list_conversation_notes(session, conv=conv, viewer=viewer)
