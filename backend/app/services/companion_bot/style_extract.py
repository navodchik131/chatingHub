"""Извлечение пар fan→reply из истории чатов для style RAG."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.db.models import Conversation, Message, MessageDirection
from app.services.chat_messages import parse_companion_message_meta
from app.services.translation import detect_lang

_FAN_MIN_LEN = 2
_FAN_MAX_LEN = 600
_REPLY_MIN_LEN = 2
_REPLY_MAX_LEN = 520
_MAX_GAP = timedelta(hours=36)
_LOOKAHEAD = 6

_SPAM_RE = re.compile(r"^(ok+|yes+|no+|да+|нет+|👍+|❤️+)$", re.IGNORECASE)
_URL_ONLY_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


@dataclass(frozen=True)
class StylePairCandidate:
    fan_message: str
    model_reply: str
    lang: str
    tags: tuple[str, ...]
    quality_score: float
    is_human: bool
    source_conversation_id: int
    source_inbound_message_id: int
    source_outbound_message_id: int
    studio_model_id: int | None


def _fan_text(msg: Message) -> str:
    return (msg.text_original or msg.text_translated or "").strip()


def _reply_text(msg: Message) -> str:
    return (msg.text_translated or msg.text_original or "").strip()


def _is_bot_outbound(msg: Message) -> bool:
    is_bot, _ = parse_companion_message_meta(getattr(msg, "meta", None))
    return is_bot


def _quality_for_outbound(
    msg: Message,
    *,
    bot_ratings: dict[int, int | None],
) -> tuple[float, bool]:
    if _is_bot_outbound(msg):
        rating = bot_ratings.get(msg.id)
        if rating == -1:
            return 0.0, False
        if rating == 1:
            return 1.4, True
        return 0.0, False
    if msg.sender_user_id:
        return 2.2, True
    return 1.6, True


def _is_usable_text(text: str, *, min_len: int, max_len: int) -> bool:
    t = (text or "").strip()
    if len(t) < min_len or len(t) > max_len:
        return False
    if _SPAM_RE.match(t):
        return False
    if _URL_ONLY_RE.match(t):
        return False
    if t.count("\n") > 4:
        return False
    return True


def _infer_tags(fan_text: str) -> tuple[str, ...]:
    low = fan_text.lower()
    tags: list[str] = []
    if any(w in low for w in ("привет", "hey", "hi", "hello", "здаров")):
        tags.append("greeting")
    if "?" in fan_text:
        tags.append("question")
    if any(w in low for w in ("что дела", "what are you", "what u up", "чем занят")):
        tags.append("checkin")
    if any(w in low for w in ("скуч", "bored", "miss", "скуча")):
        tags.append("retention")
    if any(w in low for w in ("бот", "ghost", "игнор", "annoy")):
        tags.append("trust")
    if any(w in low for w in ("hot", "sexy", "красив", "мила")):
        tags.append("flirt")
    if len(fan_text) <= 24:
        tags.append("short")
    return tuple(tags)


def extract_pairs_from_messages(
    messages: list[Message],
    *,
    conv: Conversation,
    bot_ratings: dict[int, int | None],
) -> list[StylePairCandidate]:
    if len(messages) < 2:
        return []

    out: list[StylePairCandidate] = []
    for i, msg in enumerate(messages):
        if msg.direction != MessageDirection.inbound:
            continue
        fan = _fan_text(msg)
        if not _is_usable_text(fan, min_len=_FAN_MIN_LEN, max_len=_FAN_MAX_LEN):
            continue
        if not msg.created_at:
            continue

        for j in range(i + 1, min(i + 1 + _LOOKAHEAD, len(messages))):
            nxt = messages[j]
            if nxt.direction == MessageDirection.inbound:
                break
            if nxt.direction != MessageDirection.outbound:
                continue
            if not nxt.created_at:
                break
            if nxt.created_at - msg.created_at > _MAX_GAP:
                break

            reply = _reply_text(nxt)
            if not _is_usable_text(reply, min_len=_REPLY_MIN_LEN, max_len=_REPLY_MAX_LEN):
                break

            quality, keep = _quality_for_outbound(nxt, bot_ratings=bot_ratings)
            if not keep:
                break

            lang = detect_lang(fan).lower().strip()[:2]
            if not lang or lang == "unknown":
                lang = detect_lang(reply).lower().strip()[:2] or "en"
            if len(lang) > 2:
                lang = lang[:2]

            out.append(
                StylePairCandidate(
                    fan_message=fan,
                    model_reply=reply,
                    lang=lang,
                    tags=_infer_tags(fan),
                    quality_score=quality,
                    is_human=not _is_bot_outbound(nxt),
                    source_conversation_id=conv.id,
                    source_inbound_message_id=msg.id,
                    source_outbound_message_id=nxt.id,
                    studio_model_id=conv.studio_model_id,
                )
            )
            break
    return out
