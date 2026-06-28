"""Генерация текста ответа через LLM."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    CompanionConversationState,
    Conversation,
    ConversationNote,
    ConversationNoteKind,
    Message,
    UserStudioModel,
)
from app.services.companion_bot.memory import maybe_refresh_companion_memory
from app.services.companion_bot.persona import parse_companion_persona
from app.services.companion_bot.prompt import (
    PROMPT_VERSION,
    build_companion_system_prompt,
    build_companion_user_prompt,
    last_fan_message_text,
    recent_outbound_texts,
    reply_too_similar_to_recent,
    resolve_target_lang,
)
from app.services.studio_keys import load_owner_studio_billing, studio_llm_credentials
from app.services.studio_openai import _chat_completion_text

log = logging.getLogger(__name__)

_NOTE_KINDS = (
    ConversationNoteKind.ai_profile,
    ConversationNoteKind.ai_daily,
    ConversationNoteKind.ai_insight,
)


async def _load_notes(session: AsyncSession, conv_id: int) -> list[ConversationNote]:
    return list(
        (
            await session.scalars(
                select(ConversationNote).where(
                    ConversationNote.conversation_id == conv_id,
                    ConversationNote.kind.in_(_NOTE_KINDS),
                )
            )
        ).all()
    )


async def _load_or_create_state(
    session: AsyncSession, conv_id: int
) -> CompanionConversationState:
    row = await session.get(CompanionConversationState, conv_id)
    if row:
        return row
    row = CompanionConversationState(conversation_id=conv_id, relationship_score=25)
    session.add(row)
    await session.flush()
    return row


async def generate_companion_reply(
    session: AsyncSession,
    *,
    owner_id: int,
    conv: Conversation,
    messages: list[Message],
    studio_model_id: int,
    followup: bool = False,
) -> tuple[str, str, str, int, dict]:
    """
    Возвращает (reply_text, target_lang, model_name, relationship_score, state_snapshot).
    """
    model_row = await session.get(UserStudioModel, studio_model_id)
    if not model_row or model_row.user_id != owner_id:
        raise RuntimeError("studio model not found")

    state = await _load_or_create_state(session, conv.id)

    sub, llm_row, _, plan, _, _ = await load_owner_studio_billing(session, owner_id)
    cred = studio_llm_credentials(plan=plan, llm_row=llm_row)

    memory_refreshed = await maybe_refresh_companion_memory(
        session,
        conv=conv,
        messages=messages,
        credentials=cred,
    )
    notes = await _load_notes(session, conv.id)

    target_lang = resolve_target_lang(conv, last_fan_text=last_fan_message_text(messages))
    persona = parse_companion_persona(model_row.companion_persona_json)
    system = build_companion_system_prompt(
        persona_name=model_row.name,
        persona_profile=model_row.profile_text,
        persona=persona,
        target_lang=target_lang,
        relationship_score=state.relationship_score,
        mood=state.mood,
        notes=notes,
        messages=messages,
        followup=followup,
    )

    model = (settings.openai_studio_model or "").strip() or "gpt-4o-mini"
    recent = recent_outbound_texts(messages, limit=4)
    extra_avoid: str | None = None
    reply = ""

    for attempt in range(3):
        user_msg = build_companion_user_prompt(
            conv=conv,
            messages=messages,
            followup=followup,
            extra_avoid=extra_avoid,
        )
        raw = await _chat_completion_text(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=500,
            temperature=0.72 if attempt == 0 else 0.85,
            credentials=cred,
            timeout_seconds=90.0,
        )
        reply = (raw or "").strip()
        if not reply:
            raise RuntimeError("empty companion reply")
        if not reply_too_similar_to_recent(reply, recent):
            break
        if attempt < 2:
            snippets = " | ".join(
                t.replace("\n", " ").strip()[:120] for t in recent[:3] if t.strip()
            )
            extra_avoid = (
                "Do NOT reuse these themes, questions, or phrases: "
                f"{snippets or 'your last few messages'}"
            )
            log.info(
                "companion reply too similar conv=%s attempt=%s",
                conv.id,
                attempt + 1,
            )

    snapshot = {
        "relationship_score": state.relationship_score,
        "mood": state.mood,
        "target_lang": target_lang,
        "prompt_version": PROMPT_VERSION,
        "followup": followup,
        "memory_refreshed": memory_refreshed,
    }
    return reply, target_lang, model, state.relationship_score, snapshot
