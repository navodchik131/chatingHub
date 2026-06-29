"""Промпт для генерации ответа компаньона."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.db.models import Conversation, ConversationNote, ConversationNoteKind, Message, MessageDirection
from app.services.companion_bot.persona import CompanionPersona, format_companion_persona_block
from app.services.chat_message_meta import parse_reactions
from app.services.translation import detect_lang

PROMPT_VERSION = "v5-chatter-canon-direct-2"

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
    "как бот",
    "ты бот",
    "you're a bot",
    "you are a bot",
    "talking like a bot",
    "sound like a bot",
    "обманул",
    "обманула",
    "не уходи от тем",
    "не уходишь от тем",
    "от темы не уход",
    "stop dodging",
    "avoiding the question",
)

_FACTUAL_TOPIC_HINTS = (
    "врем",
    "который час",
    "what time",
    "сколько сейчас",
    "со скольк",
    "до скольк",
    "график",
    "на работ",
    "на работе",
    "дома",
    "приед",
    "придёш",
    "придеш",
    "когда вы",
    "when do you work",
    "work hours",
    "опозд",
)

_DIRECT_QUESTION_RE = re.compile(
    r"("
    r"сколько\s+(у\s+тебя\s+)?врем|"
    r"который\s+час|"
    r"what\s+time|"
    r"со\s+скольк|"
    r"до\s+скольк|"
    r"когда\s+(ты\s+)?(приед|прид|выез|на\s+работ)|"
    r"ты\s+(на\s+)?работ|"
    r"почему\s+(.{0,40})?(дома|не\s+на\s+работ)|"
    r"ты\s+меня\s+обман|"
    r"не\s+уходи\s+от\s+тем|"
    r"в\s+смысле|"
    r"в\s+итоге"
    r")",
    re.IGNORECASE,
)

_STALE_HOOK_HINTS = (
    "зал",
    "gym",
    "трениров",
    "workout",
    "размин",
    "напряжен",
    "tension",
    "разогрел",
    "втянул",
)

_TZ_OFFSET_RE = re.compile(r"(?:UTC|GMT)\s*([+-]\d{1,2})", re.IGNORECASE)
_TZ_PLAIN_OFFSET_RE = re.compile(r"^[+-]\d{1,2}(?::\d{2})?$")


@dataclass(frozen=True)
class ThreadSignals:
    mid_conversation: bool
    greeting_reset: bool
    fan_complaint: bool
    trust_repair: bool
    direct_factual: bool
    factual_pressure: bool
    casual_checkin: bool
    last_fan_text: str | None


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
        if _trailing_hook_too_similar(cand, prev):
            return True
    return False


def _trailing_hook_too_similar(candidate: str, previous: str) -> bool:
    """Ловит один и тот же «крючок» в конце (зал / напряжение / тренировка)."""
    cand_tail = _last_sentence((candidate or "").strip()).lower()
    prev_tail = _last_sentence((previous or "").strip()).lower()
    if not cand_tail or not prev_tail:
        return False
    if not (cand_tail.endswith("?") and prev_tail.endswith("?")):
        return False
    cand_hooks = {h for h in _STALE_HOOK_HINTS if h in cand_tail}
    prev_hooks = {h for h in _STALE_HOOK_HINTS if h in prev_tail}
    if not cand_hooks or not prev_hooks:
        return False
    return bool(cand_hooks & prev_hooks)


def _last_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return parts[-1] if parts else text


def parse_persona_utc_offset(tz_str: str | None) -> timezone | None:
    raw = (tz_str or "").strip()
    if not raw:
        return None
    m = _TZ_OFFSET_RE.search(raw)
    if m:
        hours = int(m.group(1))
        return timezone(timedelta(hours=hours))
    if _TZ_PLAIN_OFFSET_RE.match(raw):
        sign = 1 if raw.startswith("+") else -1
        hours = int(raw[1:].split(":")[0])
        return timezone(timedelta(hours=sign * hours))
    return None


def persona_local_time_block(
    persona: CompanionPersona,
    *,
    now: datetime | None = None,
) -> str:
    utc_now = now or datetime.now(timezone.utc)
    if utc_now.tzinfo is None:
        utc_now = utc_now.replace(tzinfo=timezone.utc)
    tz = parse_persona_utc_offset(persona.timezone)
    label = (persona.timezone or "").strip() or "UTC"
    if tz is None:
        return f"Character local time: unknown offset — use Time (UTC) below only.\n"
    local = utc_now.astimezone(tz)
    return (
        f"Character local time ({label}): {local.strftime('%Y-%m-%d %H:%M')} "
        f"(weekday: {local.strftime('%A')}).\n"
        "When the fan asks what time it is for you, answer ONLY this local time — "
        "never UTC and never transcript [HH:MM] if they differ.\n"
    )


def _message_local_time_str(m: Message, tz: timezone | None) -> str:
    if not m.created_at:
        return ""
    dt = m.created_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    if tz is not None:
        dt = dt.astimezone(tz)
    return dt.strftime("%H:%M")


def _is_casual_checkin(text: str | None) -> bool:
    """«Что делаешь?» — не допрос про график."""
    t = (text or "").strip().lower()
    if not t:
        return False
    hints = (
        "что делаешь",
        "чем занят",
        "чем занята",
        "как день",
        "что нового",
        "what are you doing",
        "whatcha doing",
        "wyd",
        "what you up to",
    )
    return any(h in t for h in hints)


def fan_asks_direct_factual(text: str | None) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _is_casual_checkin(t):
        return False
    if _DIRECT_QUESTION_RE.search(t):
        return True
    low = t.lower()
    return "?" in t and any(h in low for h in _FACTUAL_TOPIC_HINTS)


def _fan_factual_pressure(messages: list[Message], *, last_fan_text: str | None) -> bool:
    if _is_casual_checkin(last_fan_text):
        return False
    inbound = [
        _message_text_for_transcript(m)
        for m in messages
        if m.direction == MessageDirection.inbound
    ][-3:]
    hits = sum(
        1
        for t in inbound
        if t and (fan_asks_direct_factual(t) or any(h in t.lower() for h in _FACTUAL_TOPIC_HINTS))
    )
    return hits >= 2


def _canon_facts_block(persona: CompanionPersona) -> str:
    lines = [
        "CANON FACTS (from character sheet — law; never contradict in one thread):",
    ]
    if persona.lifestyle and persona.lifestyle.strip():
        lines.append(f"- Daily life / work: {persona.lifestyle.strip()}")
    loc = ", ".join(p for p in (persona.city, persona.country) if p and p.strip())
    if loc:
        lines.append(f"- Location: {loc}")
    if persona.backstory and persona.backstory.strip():
        lines.append(f"- Backstory anchors: {persona.backstory.strip()[:600]}")
    if len(lines) == 1:
        return ""
    lines.extend(
        [
            "- If your earlier message conflicted with CANON, admit briefly (late, still home, mixed up) — "
            "do NOT invent new hours like «с 11 до 7» or «график сдвинулся» unless memory notes say so.",
            "- Work schedule in CANON is fixed unless notes explicitly say otherwise today.",
        ]
    )
    return "\n".join(lines) + "\n\n"


def _chatter_role_block(*, persona_name: str) -> str:
    return (
        "ROLE: You are a senior OnlyFans/Fanvue chatter with years of experience.\n"
        f"You write ONE outbound message as {persona_name} in first person — warm, human, concise.\n"
        "Sound like a real person texting, not an analyst or narrator.\n"
        "The fan must not suspect a bot: never mention AI, scripts, policies, or being a chatter.\n"
        "Never say «не бот», «я не бот», «not a bot» — real people don't volunteer that.\n"
        "Your job: react to their LAST message first, keep continuity, build rapport — not a persona monologue.\n"
    )


def _voice_rules() -> str:
    return (
        "VOICE (casual human texting):\n"
        "- Mirror the fan's register from the transcript: slang, abbreviations, emojis, sentence length.\n"
        "- Short beats beat essays — most replies are 1–2 lines, same vibe as their last messages.\n"
        "- Never catalog or narrate visible details (hair, clothes, objects) — real people react: "
        "«who's that?», «lol what», «is that you?», tease, laugh, get jealous.\n"
        "- No formal, literary, or «smart» phrasing — avoid lecturer tone and terminology dumps.\n"
        "- Follow persona Texting style when set; otherwise copy how the fan actually writes.\n"
        "- Many real texts end on a statement — do NOT tack on a question every single time.\n"
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


def analyze_thread_signals(messages: list[Message]) -> ThreadSignals:
    inbound = [m for m in messages if m.direction == MessageDirection.inbound]
    outbound = [m for m in messages if m.direction == MessageDirection.outbound]
    last_fan_text = _message_text_for_transcript(inbound[-1]) if inbound else None

    mid = len(inbound) >= 2 and len(outbound) >= 1
    greeting_reset = bool(last_fan_text and mid and _is_casual_greeting(last_fan_text))
    complaint = False
    for m in reversed(inbound[-6:]):
        t = _message_text_for_transcript(m)
        if t and _fan_recently_complained(t):
            complaint = True
            break

    trust_repair = bool(last_fan_text and _fan_recently_complained(last_fan_text))
    casual = _is_casual_checkin(last_fan_text)

    direct = False if casual else fan_asks_direct_factual(last_fan_text)
    if not direct and not casual:
        direct = _fan_factual_pressure(messages, last_fan_text=last_fan_text)
    if not direct and trust_repair:
        for m in reversed(inbound[-4:]):
            t = _message_text_for_transcript(m)
            if not t:
                continue
            low = t.lower()
            if fan_asks_direct_factual(t) or any(h in low for h in _FACTUAL_TOPIC_HINTS):
                direct = True
                break

    pressure = (not casual) and (
        _fan_factual_pressure(messages, last_fan_text=last_fan_text) or (trust_repair and direct)
    )

    return ThreadSignals(
        mid_conversation=mid,
        greeting_reset=greeting_reset,
        fan_complaint=complaint,
        trust_repair=trust_repair,
        direct_factual=direct or pressure,
        factual_pressure=pressure,
        casual_checkin=casual,
        last_fan_text=last_fan_text,
    )


def _analyze_thread(messages: list[Message]) -> tuple[bool, bool, bool, str | None]:
    sig = analyze_thread_signals(messages)
    return sig.mid_conversation, sig.greeting_reset, sig.fan_complaint, sig.last_fan_text


def _continuity_rules(
    *,
    signals: ThreadSignals,
) -> str:
    lines = [
        "CONVERSATION DISCIPLINE (critical):\n",
        "- Read the FULL transcript with timestamps — ongoing chat, not a cold open.",
        "- Reply to what they JUST said before adding anything new.",
        "- NEVER reuse opening greetings (hi, hey, hello, привет) mid-thread.",
        "- Do NOT repeat themes/phrases from your last 3 outbound messages (check the ban list below).",
        "- One clear emotional beat per message — not a checklist of small talk.",
        "- Avoid template fillers: «how's your day», «hope you're…», «safe drive», «text me when» unless truly new.",
        "- If they answered your question, do NOT ask the same question again in other words.",
        "- Do NOT end every reply with a question — statements and short acknowledgments are human too.",
    ]
    if signals.mid_conversation:
        lines.append("- ACTIVE THREAD: you were talking minutes ago — continue, don't reset.")
    if signals.greeting_reset:
        lines.append(
            "- Fan said hello again mid-chat — light tease or continue the thread; not a fresh intro."
        )
    if signals.fan_complaint and signals.trust_repair:
        lines.append(
            "- Fan just said you sound like a bot or dodged — acknowledge briefly, answer the fact, "
            "no «не бот», no schedule lecture unless they asked."
        )
    elif signals.fan_complaint:
        lines.append(
            "- Fan showed annoyance earlier — stay clear and human; don't repeat old mistakes."
        )
    if (signals.direct_factual or signals.factual_pressure) and not signals.casual_checkin:
        lines.append(
            "- FACTUAL THREAD: fan wants a straight answer (time, work, schedule, location). "
            "First sentence = direct answer using CANON FACTS and character local time. "
            "Do NOT redirect to gym/training/tension/flirt until they change topic."
        )
    if signals.casual_checkin:
        lines.append(
            "- Casual «what are you doing?» — one short line about your moment; "
            "don't dump work schedule or say «не бот»."
        )
    if signals.factual_pressure:
        lines.append(
            "- They asked similar factual questions several times — answer plainly again, shorter; "
            "do NOT append another rephrased closing question."
        )
    return "\n".join(lines) + "\n"


def _initiative_rules(*, followup: bool, signals: ThreadSignals) -> str:
    base = (
        "CHATTER CRAFT:\n"
        "- Mirror their energy and length; emojis only if they use them or persona style allows.\n"
        "- React to their point first — surprise, warmth, tease — only when it fits; skip if they need facts.\n"
        "- At most ONE optional hook — and skip the hook entirely if they are upset or asking concrete questions.\n"
        "- Use memory notes about the fan when relevant; don't invent facts not in transcript/notes/CANON.\n"
        "- If the fan sent an image: read the INTERNAL IMAGE NOTE below but do NOT quote or paraphrase it — "
        "react humanly (surprise, laugh, «who's that?», «is that you?», playful jealousy).\n"
        "- Banned stale hooks when fan moved on: do NOT keep asking about gym, workout, разминка, «напряжение», "
        "«разогрелся» if those already appear in YOUR RECENT OUTBOUND or fan switched to work/time topic.\n"
    )
    if followup:
        return (
            base
            + "- FOLLOW-UP ONLY: fan silent after your last text. ONE short line — new angle or gentle bump, "
            "NOT a paraphrase of your previous message. Never needy. Skip if they said they're busy.\n"
        )
    if signals.casual_checkin:
        return base + "- Keep it light — statement is enough, no interrogation at the end.\n"
    if signals.direct_factual or signals.trust_repair:
        return base + "- End on the answer — question optional only if genuinely new, not a recycled flirt hook.\n"
    return base + "- End naturally; questions are optional, not mandatory every time.\n"


def _format_recent_outbound_ban(recent: list[str]) -> str:
    if not recent:
        return ""
    lines = ["YOUR RECENT OUTBOUND (do NOT repeat phrases, questions, or topics from these):"]
    for i, text in enumerate(recent[:4], 1):
        snippet = text.replace("\n", " ").strip()
        if len(snippet) > 220:
            snippet = snippet[:219].rstrip() + "…"
        lines.append(f"{i}. {snippet}")
    tails = [_last_sentence(t) for t in recent[:3] if t.strip()]
    if tails:
        lines.append(
            "Do NOT reuse these closing hooks (especially trailing questions): "
            + " | ".join(t.replace("\n", " ")[:100] for t in tails)
        )
    return "\n".join(lines) + "\n\n"


def _format_transcript(
    messages: list[Message],
    fan_name: str | None,
    *,
    persona: CompanionPersona | None = None,
) -> str:
    lines: list[str] = []
    if fan_name:
        lines.append(f"Fan display name: {fan_name}")
    tz = parse_persona_utc_offset(persona.timezone) if persona else None
    if tz is not None:
        lines.append("Transcript times are character-local (persona timezone).")
    for m in messages:
        who = "Fan" if m.direction == MessageDirection.inbound else "You"
        text = _message_text_for_transcript(m)
        if not text and m.direction == MessageDirection.inbound and getattr(m, "attachments", None):
            text = "[sent an image]"
        if not text:
            continue
        ts = ""
        if m.created_at:
            ts = _message_local_time_str(m, tz) if tz else m.created_at.strftime("%H:%M")
            lines.append(f"[{ts}] {who}: {text}")
        else:
            lines.append(f"{who}: {text}")
    return "\n".join(lines)


def _format_fan_reactions_block(message: Message | None) -> str:
    if not message:
        return ""
    reactions = parse_reactions(getattr(message, "reactions_json", None))
    peer = [r["emoji"] for r in reactions if r.get("actor") == "peer" and r.get("emoji")]
    if not peer:
        return ""
    return f"Fan reacted to this message: {' '.join(peer)}\n"


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
    signals = analyze_thread_signals(messages)

    profile_block = format_companion_persona_block(
        name=persona_name,
        profile_text=persona_profile,
        persona=persona,
    )
    canon = _canon_facts_block(persona)
    local_time = persona_local_time_block(persona)
    note_lines: list[str] = []
    for n in notes:
        if n.kind == ConversationNoteKind.ai_profile:
            note_lines.append(f"Memory — fan profile:\n{n.content}")
        elif n.kind == ConversationNoteKind.ai_daily:
            note_lines.append(f"Memory — recent context:\n{n.content}")
        elif n.kind == ConversationNoteKind.ai_insight:
            note_lines.append(f"Chatter hint:\n{n.content}")

    mood_line = mood or "warm, playful, grounded"
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        _chatter_role_block(persona_name=persona_name)
        + canon
        + f"Character sheet (voice & facts for {persona_name}):\n{profile_block}\n\n"
        f"Relationship warmth: {relationship_score}/100.\n"
        f"Mood subtext: {mood_line}.\n"
        f"Time (UTC): {now_utc}.\n"
        + local_time
        + "\n"
        f"Language: reply ONLY in '{target_lang}' — match the fan's latest message language.\n"
        f"{_voice_rules()}"
        f"{_continuity_rules(signals=signals)}"
        f"{_initiative_rules(followup=followup, signals=signals)}"
        "Output: single chat message only — no markdown, no quotes, no labels.\n"
        + ("\n".join(note_lines) + "\n" if note_lines else "")
    )


def build_companion_user_prompt(
    *,
    conv: Conversation,
    messages: list[Message],
    followup: bool = False,
    extra_avoid: str | None = None,
    fan_image_description: str | None = None,
    trigger_message: Message | None = None,
    persona: CompanionPersona | None = None,
) -> str:
    transcript = _format_transcript(messages, conv.user_display_name, persona=persona)
    signals = analyze_thread_signals(messages)
    recent = recent_outbound_texts(messages, limit=4)

    tail = transcript[-14000:]
    focus = ""
    if not followup:
        if fan_image_description:
            focus += (
                "\n\nFan's latest message includes an IMAGE. INTERNAL note for you only "
                "(do NOT quote, list, or paraphrase these details in your reply):\n"
                f"{fan_image_description.strip()}\n"
                "React like a real person texting — emotion + one short line or question, not a photo description.\n"
            )
        if signals.last_fan_text:
            focus += f"\nFan's latest text (answer THIS first):\n{signals.last_fan_text}\n"
        elif fan_image_description:
            focus += (
                "\nFan sent image only — react to the gist from the internal note, "
                "not by describing the picture.\n"
            )
        if signals.casual_checkin:
            focus += (
                "\nCASUAL CHECK-IN: fan asked what you're doing — one short human line "
                "(e.g. дома, собираюсь на работу, кофе). No schedule dump, no «не бот», "
                "no defending yourself unless they accused you in THIS message.\n"
            )
        elif signals.direct_factual or signals.factual_pressure:
            focus += (
                "\nDIRECT ANSWER REQUIRED: concrete question about time, work, schedule, or trust. "
                "Sentence 1 = plain answer from CANON FACTS + character local time. "
                "No gym/tension/flirt redirect. No recycled closing question from recent outbound.\n"
            )
        if signals.trust_repair:
            focus += (
                "\nTRUST REPAIR: fan just challenged you — acknowledge, answer the fact, "
                "do not say «не бот». No tease pivot.\n"
            )
        focus += _format_fan_reactions_block(trigger_message)
        if signals.greeting_reset and signals.last_fan_text:
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
