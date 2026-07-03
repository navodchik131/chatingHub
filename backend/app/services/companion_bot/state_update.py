"""Обновление CompanionConversationState после отправки ответа."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CompanionConversationState

_MOOD_HINTS: list[tuple[str, str]] = [
    ("playful", r"😉|😏|хах|lol|lmao|шут"),
    ("warm", r"❤|💋|miss|скуч|люб"),
    ("tired", r"устал|устала|sleep|спать|exhaust"),
    ("busy", r"работ|busy|занят|занята|meeting"),
    ("flirty", r"hot|sexy|красив|gorgeous|baby|малыш"),
]


def _infer_mood(text: str) -> str | None:
    low = text.lower()
    for mood, pattern in _MOOD_HINTS:
        if re.search(pattern, low, re.IGNORECASE):
            return mood
    return None


def _hook_from_reply(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", t)
    return (parts[0] if parts else t)[:160]


async def update_companion_state_after_send(
    session: AsyncSession,
    *,
    conv_id: int,
    reply_text: str,
    followup: bool = False,
    state_snapshot: dict | None = None,
) -> None:
    row = await session.get(CompanionConversationState, conv_id)
    if not row:
        row = CompanionConversationState(conversation_id=conv_id, relationship_score=25)
        session.add(row)
        await session.flush()

    bump = 1 if followup else 2
    row.relationship_score = min(100, int(row.relationship_score or 25) + bump)

    inferred = _infer_mood(reply_text)
    if inferred:
        row.mood = inferred
    elif not row.mood:
        row.mood = "warm, playful"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily: dict = {}
    if row.daily_state_json:
        try:
            parsed = json.loads(row.daily_state_json)
            if isinstance(parsed, dict):
                daily = parsed
        except json.JSONDecodeError:
            daily = {}

    if daily.get("date") != today:
        daily = {"date": today, "topics": [], "outbound_count": 0}

    hook = _hook_from_reply(reply_text)
    if hook:
        topics = list(daily.get("topics") or [])
        if hook not in topics:
            topics.append(hook)
        daily["topics"] = topics[-6:]
    daily["outbound_count"] = int(daily.get("outbound_count") or 0) + 1
    daily["last_hook"] = hook
    if state_snapshot:
        daily["last_prompt_version"] = state_snapshot.get("prompt_version")

    row.daily_state_json = json.dumps(daily, ensure_ascii=False)
    row.updated_at = datetime.now(timezone.utc)
