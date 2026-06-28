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
from app.services.companion_bot.persona import parse_companion_persona
from app.services.companion_bot.prompt import (
    PROMPT_VERSION,
    build_companion_system_prompt,
    build_companion_user_prompt,
    resolve_target_lang,
)
from app.services.studio_keys import load_owner_studio_billing, studio_llm_credentials
from app.services.studio_openai import _chat_completion_text

log = logging.getLogger(__name__)


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
    notes = list(
        (
            await session.scalars(
                select(ConversationNote).where(
                    ConversationNote.conversation_id == conv.id,
                    ConversationNote.kind.in_(
                        [
                            ConversationNoteKind.ai_profile,
                            ConversationNoteKind.ai_daily,
                        ]
                    ),
                )
            )
        ).all()
    )

    target_lang = resolve_target_lang(conv)
    persona = parse_companion_persona(model_row.companion_persona_json)
    system = build_companion_system_prompt(
        persona_name=model_row.name,
        persona_profile=model_row.profile_text,
        persona=persona,
        target_lang=target_lang,
        relationship_score=state.relationship_score,
        mood=state.mood,
        notes=notes,
        followup=followup,
    )
    user_msg = build_companion_user_prompt(conv=conv, messages=messages, followup=followup)

    sub, llm_row, _, plan, _, _ = await load_owner_studio_billing(session, owner_id)
    cred = studio_llm_credentials(plan=plan, llm_row=llm_row)
    model = (settings.openai_studio_model or "").strip() or "gpt-4o-mini"

    raw = await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=500,
        temperature=0.85,
        credentials=cred,
        timeout_seconds=90.0,
    )
    reply = (raw or "").strip()
    if not reply:
        raise RuntimeError("empty companion reply")

    snapshot = {
        "relationship_score": state.relationship_score,
        "mood": state.mood,
        "target_lang": target_lang,
        "prompt_version": PROMPT_VERSION,
        "followup": followup,
    }
    return reply, target_lang, model, state.relationship_score, snapshot
