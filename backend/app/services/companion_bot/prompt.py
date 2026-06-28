"""Промпт для генерации ответа компаньона."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import Conversation, ConversationNote, ConversationNoteKind, Message, MessageDirection

PROMPT_VERSION = "v1"


def resolve_target_lang(conv: Conversation) -> str:
    forced = (conv.outbound_lang or "").strip().lower()
    if forced:
        return forced
    return (conv.user_lang or "en").strip().lower() or "en"


def _format_transcript(messages: list[Message], fan_name: str | None) -> str:
    lines: list[str] = []
    if fan_name:
        lines.append(f"Fan display name: {fan_name}")
    for m in messages:
        who = "Fan" if m.direction == MessageDirection.inbound else "You"
        text = (m.text_original or m.text_translated or "").strip()
        if not text:
            continue
        lines.append(f"{who}: {text}")
    return "\n".join(lines)


def build_companion_system_prompt(
    *,
    persona_name: str,
    persona_profile: str,
    target_lang: str,
    relationship_score: int,
    mood: str | None,
    notes: list[ConversationNote],
) -> str:
    profile_block = (persona_profile or "").strip() or "Young woman, warm and playful."
    note_lines: list[str] = []
    for n in notes:
        if n.kind == ConversationNoteKind.ai_profile:
            note_lines.append(f"Known about fan:\n{n.content}")
        elif n.kind == ConversationNoteKind.ai_daily:
            note_lines.append(f"Recent context:\n{n.content}")

    mood_line = mood or "neutral, slightly flirty"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        f"You are {persona_name}, a real woman chatting with a fan. Never say you are AI or a bot.\n"
        f"Persona profile:\n{profile_block}\n\n"
        f"Relationship warmth: {relationship_score}/100 (higher = more open, personal, flirty).\n"
        f"Current mood: {mood_line}.\n"
        f"Local time reference: {now}.\n\n"
        f"Reply ONLY in language code '{target_lang}'. Use natural casual speech, emojis when fitting, "
        f"local slang and texting style for that language. Match the fan's message length and energy.\n"
        "Stay in character. Remember prior context. Do not repeat yourself. "
        "One message only — no markdown headers, no quotes, no role labels.\n"
        + ("\n".join(note_lines) + "\n" if note_lines else "")
    )


def build_companion_user_prompt(
    *,
    conv: Conversation,
    messages: list[Message],
) -> str:
    transcript = _format_transcript(messages, conv.user_display_name)
    return f"Conversation so far:\n\n{transcript[-14000:]}\n\nWrite your next reply as the persona."
