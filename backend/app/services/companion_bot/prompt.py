"""Промпт для генерации ответа компаньона."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.db.models import Conversation, ConversationNote, ConversationNoteKind, Message, MessageDirection
from app.services.companion_bot.persona import CompanionPersona, format_companion_persona_block
from app.services.translation import detect_lang

PROMPT_VERSION = "v4-chatter"

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
    "same thing",
    "одно и то же",
)


def recent_outbound_texts(messages: list[Message], *, limit: int = 4) -> list[str]:
    out: list[str] = []
    for m in reversed(messages):
        if m.direction != MessageDirection.outbound:
            continue
        text = _message_text_for_transcript(m)
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _token_set(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zа-яё0-9']+", (text or "").lower()) if len(w) > 2}


def reply_too_similar_to_recent(candidate: str, recent_outbound: list[str]) -> bool:
    """Грубая проверка зацикливания на последних исходящих."""
    cand = (candidate or "").strip()
    if not cand or not recent_outbound:
        return False
    cand_low = cand.lower()
    cand_tokens = _token_set(cand)
    for prev in recent_outbound[:3]:
        prev = (prev or "").strip()
        if not prev:
            continue
        if cand_low == prev.lower():
            return True
        if len(cand) > 40 and cand_low[:40] == prev.lower()[:40]:
            return True
        prev_tokens = _token_set(prev)
        if cand_tokens and prev_tokens:
            overlap = len(cand_tokens & prev_tokens) / max(len(cand_tokens), 1)
            if overlap >= 0.62 and len(cand) > 30:
                return True
    return False


def _chatter_role_block(*, persona_name: str) -> str:
    return (
        "ROLE: You are a senior OnlyFans/Fanvue chatter with years of experience.\n"
        f"You write ONE outbound message as {persona_name} in first person — warm, human, concise.\n"
        "The fan must not suspect a bot: never mention AI, scripts, policies, or being a chatter.\n"
        "Your job: react to their LAST message first, keep continuity, build rapport — not a persona monologue.\n"
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
        "CONVERSATION DISCIPLINE (critical):\n",
        "- Read the FULL transcript with timestamps — ongoing chat, not a cold open.",
        "- Reply to what they JUST said before adding anything new.",
        "- NEVER reuse opening greetings (hi, hey, hello, привет) mid-thread.",
        "- Do NOT repeat themes/phrases from your last 3 outbound messages (check the ban list below).",
        "- One clear emotional beat per message — not a checklist of small talk.",
        "- Avoid template fillers: «how's your day», «hope you're…», «safe drive», «text me when» unless truly new.",
        "- If they answered your question, do NOT ask the same question again in other words.",
    ]
    if mid_conversation:
        lines.append("- ACTIVE THREAD: you were talking minutes ago — continue, don't reset.")
    if fan_greeting_reset:
        lines.append(
            "- Fan said hello again mid-chat — light tease or continue the thread; not a fresh intro."
        )
    if fan_complaint:
        lines.append(
            "- Fan showed annoyance or boredom — acknowledge briefly, change angle, zero repetition."
        )
    return "\n".join(lines) + "\n"


def _initiative_rules(*, followup: bool) -> str:
    base = (
        "CHATTER CRAFT:\n"
        "- Mirror their energy and length; emojis only if they use them or persona style allows.\n"
        "- Show a specific reaction (surprise, warmth, playful envy) before any new topic.\n"
        "- At most ONE hook per message — question OR tease, not both stacked.\n"
        "- Use memory notes about the fan when relevant; don't invent facts not in transcript/notes.\n"
    )
    if followup:
        return (
            base
            + "- FOLLOW-UP ONLY: fan silent after your last text. ONE short line — new angle or gentle bump, "
            "NOT a paraphrase of your previous message. Never needy. Skip if they said they're busy.\n"
        )
    return base + "- End naturally; don't force engagement bait every time.\n"


def _format_recent_outbound_ban(recent: list[str]) -> str:
    if not recent:
        return ""
    lines = ["YOUR RECENT OUTBOUND (do NOT repeat phrases, questions, or topics from these):"]
    for i, text in enumerate(recent[:4], 1):
        snippet = text.replace("\n", " ").strip()
        if len(snippet) > 220:
            snippet = snippet[:219].rstrip() + "…"
        lines.append(f"{i}. {snippet}")
    return "\n".join(lines) + "\n\n"


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
            note_lines.append(f"Memory — fan profile:\n{n.content}")
        elif n.kind == ConversationNoteKind.ai_daily:
            note_lines.append(f"Memory — recent context:\n{n.content}")
        elif n.kind == ConversationNoteKind.ai_insight:
            note_lines.append(f"Chatter hint:\n{n.content}")

    mood_line = mood or "warm, playful, grounded"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        _chatter_role_block(persona_name=persona_name)
        + f"Character sheet (voice & facts for {persona_name}):\n{profile_block}\n\n"
        f"Relationship warmth: {relationship_score}/100.\n"
        f"Mood subtext: {mood_line}.\n"
        f"Time (UTC): {now}.\n\n"
        f"Language: reply ONLY in '{target_lang}' — match the fan's latest message language.\n"
        f"{_continuity_rules(mid_conversation=mid, fan_greeting_reset=greeting_reset, fan_complaint=complaint)}"
        f"{_initiative_rules(followup=followup)}"
        "Output: single chat message only — no markdown, no quotes, no labels.\n"
        + ("\n".join(note_lines) + "\n" if note_lines else "")
    )


def build_companion_user_prompt(
    *,
    conv: Conversation,
    messages: list[Message],
    followup: bool = False,
    extra_avoid: str | None = None,
) -> str:
    transcript = _format_transcript(messages, conv.user_display_name)
    _, greeting_reset, _, last_fan_text = _analyze_thread(messages)
    recent = recent_outbound_texts(messages, limit=4)

    tail = transcript[-14000:]
    focus = ""
    if last_fan_text and not followup:
        focus = f"\n\nFan's latest message (answer THIS first):\n{last_fan_text}\n"
        if greeting_reset:
            focus += (
                "They greeted again mid-chat — do NOT greet back like a new conversation.\n"
            )

    ban_block = _format_recent_outbound_ban(recent)
    avoid = (extra_avoid or "").strip()
    if avoid:
        ban_block += f"REGENERATION: your previous draft was too repetitive. Write differently.\n{avoid}\n\n"

    if followup:
        return (
            f"Conversation so far:\n\n{tail}\n"
            f"{ban_block}"
            f"{focus}"
            "Write ONE follow-up as the character (fan has not replied to your last message)."
        )
    return (
        f"Conversation so far:\n\n{tail}\n"
        f"{ban_block}"
        f"{focus}"
        "Write the next reply. No reset, no repeated beats from your recent messages."
    )
