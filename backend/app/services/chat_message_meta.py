"""Платформенные id сообщений, реакции, цитаты."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message

REACTION_EMOJIS = ("👍", "❤️", "😂", "😮", "😢", "🔥")


def parse_reactions(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        emoji = str(item.get("emoji") or "").strip()
        actor = str(item.get("actor") or "owner").strip().lower()
        if emoji and actor in ("owner", "peer"):
            out.append({"emoji": emoji, "actor": actor})
    return out


def reactions_to_json(reactions: list[dict[str, str]]) -> str:
    return json.dumps(reactions, ensure_ascii=False)


def toggle_owner_reaction(reactions: list[dict[str, str]], emoji: str) -> list[dict[str, str]]:
    emoji = emoji.strip()
    if not emoji:
        return reactions
    kept = [r for r in reactions if not (r.get("actor") == "owner" and r.get("emoji") == emoji)]
    if len(kept) == len(reactions):
        kept.append({"emoji": emoji, "actor": "owner"})
    return kept


def sync_actor_reactions(
    reactions: list[dict[str, str]],
    *,
    actor: str,
    emojis: list[str],
) -> list[dict[str, str]]:
    """Заменить реакции одного актора (owner/peer) списком emoji из платформы."""
    kept = [r for r in reactions if r.get("actor") != actor]
    for emoji in emojis:
        em = emoji.strip()
        if em:
            kept.append({"emoji": em, "actor": actor})
    return kept


def platform_message_id_from_meta(meta: str | None) -> str | None:
    if not meta:
        return None
    try:
        data = json.loads(meta)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    for key in ("message_id", "telegram_message_id", "fanvue_message_uuid"):
        val = data.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def merge_meta_dict(meta: str | None, patch: dict[str, Any]) -> str:
    base: dict[str, Any] = {}
    if meta:
        try:
            parsed = json.loads(meta)
            if isinstance(parsed, dict):
                base = parsed
        except json.JSONDecodeError:
            pass
    base.update(patch)
    return json.dumps(base, ensure_ascii=False)


async def resolve_reply_target(
    session: AsyncSession,
    *,
    conv_id: int,
    reply_to_message_id: int | None,
) -> Message | None:
    if not reply_to_message_id:
        return None
    row = await session.scalar(
        select(Message).where(
            Message.id == reply_to_message_id,
            Message.conversation_id == conv_id,
        )
    )
    return row


def message_preview_for_reply(msg: Message) -> str:
    text = (msg.text_original or msg.text_translated or "").strip()
    if text:
        return text[:160]
    if msg.attachments:
        return "📷 Изображение"
    return "Сообщение"
