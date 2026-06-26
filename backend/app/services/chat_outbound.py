"""Исходящие сообщения чата с изображениями (Telegram / Fanvue)."""

from __future__ import annotations

import logging
import mimetypes
from io import BytesIO

import anyio
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BufferedInputFile
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BACKEND_DIR, settings
from app.connectors.fanvue.client import FanvueAPIError, send_direct_message
from app.connectors.fanvue.media import fanvue_upload_image_bytes
from app.db.models import Platform, StudioGeneration
from app.services.studio_generation_storage import generation_has_archive_file

log = logging.getLogger(__name__)


async def read_upload_image(upload: UploadFile | None) -> tuple[bytes, str] | None:
    if upload is None:
        return None
    raw = await upload.read()
    if not raw:
        return None
    ct = (upload.content_type or "image/jpeg").split(";")[0].strip() or "image/jpeg"
    if not ct.startswith("image/"):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением")
    return raw, ct


async def load_studio_generation_image_bytes(
    session: AsyncSession,
    *,
    owner_id: int,
    generation_id: int,
) -> tuple[bytes, str]:
    row = await session.get(StudioGeneration, generation_id)
    if not row or row.user_id != owner_id:
        raise HTTPException(status_code=404, detail="Генерация не найдена")
    if not generation_has_archive_file(row):
        raise HTTPException(
            status_code=404,
            detail="Файл изображения ещё не сохранён в архиве",
        )
    abs_path = (BACKEND_DIR / row.relative_path).resolve()
    try:
        abs_path.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Не найдено") from None
    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Файл изображения отсутствует")
    data = await anyio.to_thread.run_sync(abs_path.read_bytes)
    ct = (row.content_type or "").strip() or mimetypes.guess_type(abs_path.name)[0] or "image/png"
    if not ct.startswith("image/"):
        ct = "image/png"
    return data, ct


async def resolve_outbound_image(
    session: AsyncSession,
    *,
    owner_id: int,
    upload: UploadFile | None,
    studio_generation_id: int | None,
) -> tuple[bytes, str] | None:
    if upload is not None:
        return await read_upload_image(upload)
    if studio_generation_id is not None and studio_generation_id > 0:
        return await load_studio_generation_image_bytes(
            session, owner_id=owner_id, generation_id=studio_generation_id
        )
    return None


async def send_telegram_outbound(
    *,
    token: str,
    chat_id: int,
    topic_id: int,
    text: str,
    image_bytes: bytes | None,
    image_mime: str | None,
    reply_to_telegram_message_id: int | None = None,
) -> int | None:
    proxy = (settings.telegram_proxy or "").strip()
    session_aio = AiohttpSession(proxy=proxy) if proxy else None
    bot = Bot(token=token, session=session_aio) if session_aio else Bot(token=token)
    reply_kw: dict[str, int] = {}
    if reply_to_telegram_message_id is not None and reply_to_telegram_message_id > 0:
        reply_kw["reply_to_message_id"] = reply_to_telegram_message_id
    try:
        if image_bytes:
            ext = ".jpg"
            if image_mime and "png" in image_mime:
                ext = ".png"
            elif image_mime and "webp" in image_mime:
                ext = ".webp"
            photo = BufferedInputFile(image_bytes, filename=f"image{ext}")
            if (text or "").strip():
                sent = await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=text,
                    direct_messages_topic_id=topic_id,
                    **reply_kw,
                )
            else:
                sent = await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    direct_messages_topic_id=topic_id,
                    **reply_kw,
                )
        elif (text or "").strip():
            sent = await bot.send_message(
                chat_id=chat_id,
                text=text,
                direct_messages_topic_id=topic_id,
                **reply_kw,
            )
        else:
            raise HTTPException(status_code=400, detail="Пустое сообщение")
        return int(sent.message_id) if sent and sent.message_id else None
    finally:
        await bot.session.close()


async def set_telegram_message_reaction(
    *,
    token: str,
    chat_id: int,
    telegram_message_id: int,
    emoji: str,
) -> None:
    from aiogram.types import ReactionTypeEmoji

    proxy = (settings.telegram_proxy or "").strip()
    session_aio = AiohttpSession(proxy=proxy) if proxy else None
    bot = Bot(token=token, session=session_aio) if session_aio else Bot(token=token)
    try:
        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=telegram_message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)],
        )
    finally:
        await bot.session.close()


async def send_fanvue_outbound(
    *,
    access_token: str,
    fan_uuid: str,
    text: str,
    image_bytes: bytes | None,
    image_mime: str | None,
    reply_to_message_uuid: str | None = None,
) -> str | None:
    media_uuids: list[str] | None = None
    if image_bytes:
        try:
            mu = await fanvue_upload_image_bytes(
                access_token,
                filename="chat.jpg",
                raw=image_bytes,
                content_type=image_mime or "image/jpeg",
            )
            media_uuids = [mu]
        except FanvueAPIError as e:
            st = e.status if e.status >= 400 else 502
            raise HTTPException(status_code=st, detail=(e.body or str(e))[:2000]) from e
    if not (text or "").strip() and not media_uuids:
        raise HTTPException(status_code=400, detail="Пустое сообщение")
    try:
        return await send_direct_message(
            access_token,
            fan_uuid,
            text or "",
            media_uuids=media_uuids,
            reply_to_message_uuid=reply_to_message_uuid,
        )
    except FanvueAPIError as e:
        st = e.status
        if st >= 500:
            st = 502
        elif st < 400:
            st = 502
        raise HTTPException(
            status_code=st,
            detail=(e.body or str(e))[:2000],
        ) from e
