"""Vision: описание входящих фото фана для companion bot (вариант A)."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Conversation, Message, MessageDirection
from app.services.chat_attachment import resolve_chat_attachment_file
from app.services.chat_message_meta import merge_meta_dict, parse_reactions
from app.services.companion_bot.prompt import _message_text_for_transcript
from app.services.studio_keys import StudioOpenAiCredentials
from app.services.studio_openai import _chat_completion_text

log = logging.getLogger(__name__)

VISION_META_KEY = "companion_vision_description"


def read_vision_description(meta: str | None) -> str | None:
    if not meta:
        return None
    try:
        import json

        data = json.loads(meta)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    desc = str(data.get(VISION_META_KEY) or "").strip()
    return desc or None


def _recent_context_before_trigger(
    messages: list[Message],
    *,
    trigger_id: int,
    limit: int = 14,
) -> str:
    prior = [m for m in messages if m.id <= trigger_id][-limit:]
    lines: list[str] = []
    for m in prior:
        who = "Fan" if m.direction == MessageDirection.inbound else "You"
        text = _message_text_for_transcript(m)
        if text:
            lines.append(f"{who}: {text}")
        elif m.direction == MessageDirection.inbound and getattr(m, "attachments", None):
            if m.id == trigger_id:
                lines.append(f"{who}: [sent an image — see description below]")
            else:
                lines.append(f"{who}: [sent an image]")
    return "\n".join(lines)


def _peer_reaction_emojis(message: Message) -> list[str]:
    reactions = parse_reactions(getattr(message, "reactions_json", None))
    return [r["emoji"] for r in reactions if r.get("actor") == "peer" and r.get("emoji")]


async def _describe_fan_image_openai(
    *,
    image_bytes: bytes,
    image_media_type: str | None,
    caption: str,
    reaction_emojis: list[str],
    context_transcript: str,
    credentials: StudioOpenAiCredentials,
) -> str:
    model = (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model
    import base64

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    mime = (image_media_type or "image/jpeg").split(";")[0].strip()
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"

    caption_block = f'Fan caption on this image: "{caption}"\n' if caption else ""
    react_block = ""
    if reaction_emojis:
        react_block = f"Fan reactions on this message: {' '.join(reaction_emojis)}\n"

    instruction = (
        "You assist a professional OnlyFans/Fanvue chatter. The fan just sent an image in an ongoing chat.\n"
        "Study the image AND the recent conversation context.\n\n"
        f"Recent chat:\n{context_transcript or '(no prior text)'}\n\n"
        f"{caption_block}{react_block}\n"
        "Write a SHORT internal brief for the chatter ONLY — NOT text to send to the fan.\n"
        "Use plain English, 3–5 short lines (labels ok):\n"
        "- GIST: one line — main subject (e.g. woman selfie, meme, food, pet, screenshot)\n"
        "- CHAT LINK: how it ties to the thread + caption (if obvious)\n"
        "- LIKELY INTENT: joke, flex, random share, teasing, work/life update, etc.\n"
        "- REACT ANGLE: what a real texter would wonder or feel (e.g. «who is she?», «is that you?», "
        "«are you joking?», laugh it off, playful jealousy)\n"
        "Do NOT catalog every visible object (hair color, backpack brand, headphones, outfit pieces).\n"
        "At most ONE hook if it changes the reaction (e.g. clearly another woman, delivery uniform, meme).\n"
        "Do NOT invent unseen facts. Do NOT write the reply message. No markdown."
    )

    user_content: list[dict] = [
        {"type": "text", "text": instruction},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
    ]
    return await _chat_completion_text(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You output only the requested image description for a human chatter.",
            },
            {"role": "user", "content": user_content},
        ],
        max_tokens=400,
        temperature=0.35,
        credentials=credentials,
        timeout_seconds=90.0,
    )


async def maybe_describe_fan_image_for_companion(
    session: AsyncSession,
    *,
    owner_id: int,
    conv: Conversation,
    trigger: Message,
    messages: list[Message],
    credentials: StudioOpenAiCredentials | None,
) -> str | None:
    """
    Описывает первое вложение триггер-сообщения и кэширует в message.meta.
    Возвращает текст описания или None.
    """
    if not settings.companion_vision_enabled:
        return None
    if not credentials or not (credentials.api_key or "").strip():
        return None

    cached = read_vision_description(trigger.meta)
    if cached:
        return cached

    attachments = getattr(trigger, "attachments", None) or []
    if not attachments:
        return None

    att = attachments[0]
    path = resolve_chat_attachment_file(owner_id, att.relative_path)
    if not path:
        log.warning(
            "companion vision: attachment missing conv=%s msg=%s path=%s",
            conv.id,
            trigger.id,
            att.relative_path,
        )
        return None

    try:
        image_bytes = path.read_bytes()
    except OSError as e:
        log.warning("companion vision: read failed conv=%s msg=%s: %s", conv.id, trigger.id, e)
        return None

    caption = (trigger.text_original or "").strip()
    reactions = _peer_reaction_emojis(trigger)
    context = _recent_context_before_trigger(messages, trigger_id=trigger.id)

    try:
        description = (
            await _describe_fan_image_openai(
                image_bytes=image_bytes,
                image_media_type=att.mime_type,
                caption=caption,
                reaction_emojis=reactions,
                context_transcript=context,
                credentials=credentials,
            )
        ).strip()
    except Exception as e:
        log.warning("companion vision failed conv=%s msg=%s: %s", conv.id, trigger.id, e)
        return None

    if not description:
        return None

    trigger.meta = merge_meta_dict(trigger.meta, {VISION_META_KEY: description})
    await session.flush()
    log.info("companion vision described conv=%s msg=%s", conv.id, trigger.id)
    return description
