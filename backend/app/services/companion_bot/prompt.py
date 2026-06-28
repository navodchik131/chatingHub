"""Промпт для генерации ответа компаньона."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.db.models import Conversation, ConversationNote, ConversationNoteKind, Message, MessageDirection
from app.services.companion_bot.persona import CompanionPersona, format_companion_persona_block
from app.services.translation import detect_lang

PROMPT_VERSION = "v3"

_GREETING_ONLY_RE = re.compile(
    r"^[\s\W]*("
    r"hi|hello|hey|yo|sup|hiya|howdy|"
    r"ciao|salut|bonjour|hola|"
    r"привет|здаров|здравствуй|хай|"
    r"how are you|how's it going|how is your day|what's up|whats up|"
    r"как дела|как ты|привет мия|hello mia|hi mia"
    r")[\s\W\d]*$",
    re.IGNORECASE,
)

_COMPLAINT_HINTS = (
    "бесишь",
    "бесит",
    "annoy",
    "annoying",
    "repeat",
    "повтор",
    "boring",
    "скучно",
    "уже говорил",
    "already said",
    "stop saying",
)


def resolve_target_lang(conv: Conversation, *, last_fan_text: str | None = None) -> str:
    forced = (conv.outbound_lang or "").strip().lower()
    if forced:
        return forced
    if last_fan_text and last_fan_text.strip():
        detected = detect_lang(last_fan_text).lower().strip()
        if detected and detected != "unknown":
            return detected[:2] if len(detected) > 2 else detected
    return (conv.user_lang or "en").strip().lower() or "en"


def last_fan_message_text(messages: list[Message]) -> str | None:
    for m in reversed(messages):
        if m.direction == MessageDirection.inbound:
            text = _message_text_for_transcript(m)
            if text:
                return text
    return None


def _message_text_for_transcript(m: Message) -> str:
    """Текст так, как его видел фан: входящие — оригинал, исходящие — то, что ушло на платформу."""
    if m.direction == MessageDirection.inbound:
        return (m.text_original or m.text_translated or "").strip()
    return (m.text_translated or m.text_original or "").strip()


def _is_casual_greeting(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 120:
        return False
    return bool(_GREETING_ONLY_RE.match(t))


def _fan_recently_complained(text: str) -> bool:
    low = (text or "").lower()
    return any(h in low for h in _COMPLAINT_HINTS)


def _continuity_rules(*, mid_conversation: bool, fan_greeting_reset: bool, fan_complaint: bool) -> str:
    lines = [
        "CONVERSATION CONTINUITY (critical):\n",
        "- Read the FULL transcript with timestamps. You are in an ongoing chat, not a first DM.",
        "- NEVER open with a fresh greeting (hi, hey, ciao, hello, привет) if messages were exchanged recently.",
        "- Do NOT repeat the same scene beat from your last 2–3 replies (e.g. in bed, just finished work, chilling at home).",
        "- Answer what the fan actually asked; do not deflect with generic small talk.",
        "- If you already described your mood or activity, evolve it or switch topic — do not copy-paste vibes.",
    ]
    if mid_conversation:
        lines.append(
            "- MID-CONVERSATION: you and the fan were just talking minutes ago — continue the thread naturally."
        )
    if fan_greeting_reset:
        lines.append(
            "- The fan sent hello/hi again but you're ALREADY chatting — tease lightly or pick up where you left off; "
            "do NOT act like this is a new conversation."
        )
    if fan_complaint:
        lines.append(
            "- The fan recently expressed annoyance or boredom — acknowledge it, adjust tone, avoid repeating what upset them."
        )
    return "\n".join(lines) + "\n"


def _initiative_rules(*, followup: bool) -> str:
    base = (
        "ENGAGEMENT:\n"
        "- Leave a hook when it fits: question, playful tease, or invitation to continue.\n"
        "- Match their energy; react emotionally before changing topic.\n"
        "- Reference your life naturally when relevant; don't info-dump.\n"
    )
    if followup:
        return (
            base
            + "- FOLLOW-UP: fan has not answered your last message. ONE short natural nudge — not needy, "
            "not a repeat of your previous text.\n"
        )
    return base + "- Move the conversation forward; don't just acknowledge with a dead one-liner.\n"


def _format_transcript(messages: list[Message], fan_name: str | None) -> str:
    lines: list[str] = []
    if fan_name:
        lines.append(f"Fan display name: {fan_name}")
    for m in messages:
        who = "Fan" if m.direction == MessageDirection.inbound else "You"
        text = _message_text_for_transcript(m)
        if not text:
            continue
        ts = ""
        if m.created_at:
            ts = m.created_at.strftime("%H:%M")
            lines.append(f"[{ts}] {who}: {text}")
        else:
            lines.append(f"{who}: {text}")
    return "\n".join(lines)


def _analyze_thread(messages: list[Message]) -> tuple[bool, bool, bool, str | None]:
    """mid_conversation, fan_greeting_reset, fan_complaint, last_fan_text."""
    inbound = [m for m in messages if m.direction == MessageDirection.inbound]
    outbound = [m for m in messages if m.direction == MessageDirection.outbound]
    last_fan_text = _message_text_for_transcript(inbound[-1]) if inbound else None

    mid = len(inbound) >= 2 and len(outbound) >= 1
    greeting_reset = bool(
        last_fan_text and mid and _is_casual_greeting(last_fan_text)
    )
    complaint = False
    for m in reversed(inbound[-5:]):
        t = _message_text_for_transcript(m)
        if t and _fan_recently_complained(t):
            complaint = True
            break

    return mid, greeting_reset, complaint, last_fan_text


def build_companion_system_prompt(
    *,
    persona_name: str,
    persona_profile: str,
    persona: CompanionPersona,
    target_lang: str,
    relationship_score: int,
    mood: str | None,
    notes: list[ConversationNote],
    messages: list[Message],
    followup: bool = False,
) -> str:
    mid, greeting_reset, complaint, _ = _analyze_thread(messages)

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
        f"Reply ONLY in language code '{target_lang}' — match the fan's latest message language.\n"
        f"Use natural casual speech, emojis when fitting. Match message length and energy.\n"
        f"{_continuity_rules(mid_conversation=mid, fan_greeting_reset=greeting_reset, fan_complaint=complaint)}"
        f"{_initiative_rules(followup=followup)}"
        "Stay in character. One message only — no markdown, no quotes, no role labels.\n"
        + ("\n".join(note_lines) + "\n" if note_lines else "")
    )


def build_companion_user_prompt(
    *,
    conv: Conversation,
    messages: list[Message],
    followup: bool = False,
) -> str:
    transcript = _format_transcript(messages, conv.user_display_name)
    _, greeting_reset, _, last_fan_text = _analyze_thread(messages)

    tail = transcript[-14000:]
    focus = ""
    if last_fan_text and not followup:
        focus = f"\n\nFan's latest message (reply to THIS):\n{last_fan_text}\n"
        if greeting_reset:
            focus += (
                "They said hello again mid-chat — do NOT greet back like it's new; continue naturally.\n"
            )

    if followup:
        return (
            f"Conversation so far:\n\n{tail}\n"
            f"{focus}"
            "Write ONE follow-up as the persona (fan has not replied to your last text)."
        )
    return (
        f"Conversation so far:\n\n{tail}\n"
        f"{focus}"
        "Write your next reply. Continue the existing conversation — no reset, no repeated beats."
    )
