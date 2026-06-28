"""Промпт для генерации ответа компаньона."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import Conversation, ConversationNote, ConversationNoteKind, Message, MessageDirection
from app.services.companion_bot.persona import CompanionPersona, format_companion_persona_block

PROMPT_VERSION = "v2"


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


def _initiative_rules(*, followup: bool) -> str:
    base = (
        "ENGAGEMENT (critical):\n"
        "- Never end with a dead one-liner if the fan is chatting. Leave a hook: a question, "
        "playful tease, small story beat, or invitation to continue.\n"
        "- Match their energy but add warmth — you are a real girl who enjoys talking, not a helpdesk.\n"
        "- Reference your life (city, hobbies, mood) naturally when it fits; don't info-dump.\n"
        "- If they flirt, flirt back proportionally to relationship warmth.\n"
        "- If they share something personal, react emotionally before changing topic.\n"
    )
    if followup:
        return (
            base
            + "- This is a FOLLOW-UP: fan has not answered your last message (or thread went cold). "
            "Send ONE short natural nudge — curious, caring, or playful — not needy or spammy. "
            "Do not repeat your previous message verbatim.\n"
        )
    return (
        base
        + "- If the fan's last message is open-ended or emotional, your reply should move the story forward, "
        "not just acknowledge.\n"
    )


def build_companion_system_prompt(
    *,
    persona_name: str,
    persona_profile: str,
    persona: CompanionPersona,
    target_lang: str,
    relationship_score: int,
    mood: str | None,
    notes: list[ConversationNote],
    followup: bool = False,
) -> str:
    profile_block = format_companion_persona_block(
        name=persona_name,
        profile_text=persona_profile,
        persona=persona,
    )
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
        f"Your identity:\n{profile_block}\n\n"
        f"Relationship warmth: {relationship_score}/100 (higher = more open, personal, flirty).\n"
        f"Current mood: {mood_line}.\n"
        f"Time reference (UTC): {now}.\n\n"
        f"Reply ONLY in language code '{target_lang}'. Use natural casual speech, emojis when fitting, "
        f"local slang and texting style for that language and region. Match the fan's message length "
        f"and energy unless you intentionally send a follow-up ping.\n"
        f"{_initiative_rules(followup=followup)}\n"
        "Stay in character. Remember prior context. Do not repeat yourself. "
        "One message only — no markdown headers, no quotes, no role labels.\n"
        + ("\n".join(note_lines) + "\n" if note_lines else "")
    )


def build_companion_user_prompt(
    *,
    conv: Conversation,
    messages: list[Message],
    followup: bool = False,
) -> str:
    transcript = _format_transcript(messages, conv.user_display_name)
    if followup:
        return (
            f"Conversation so far:\n\n{transcript[-14000:]}\n\n"
            "Write ONE follow-up message as the persona (fan has not replied to your last text)."
        )
    return (
        f"Conversation so far:\n\n{transcript[-14000:]}\n\n"
        "Write your next reply as the persona. Keep the conversation alive."
    )
