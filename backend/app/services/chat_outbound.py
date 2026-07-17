"""Исходящие сообщения чата с изображениями (Telegram / Fanvue / Instagram)."""

from __future__ import annotations

import logging
import mimetypes

import anyio
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BufferedInputFile
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BACKEND_DIR, settings
from app.connectors.fanvue.client import FanvueAPIError, send_direct_message
from app.connectors.fanvue.media import fanvue_upload_image_bytes
from app.connectors.instagram.client import InstagramAPIError, send_instagram_message
from app.db.models import StudioGeneration, StudioMotionRender
from app.services.chat_attachment import chat_media_public_absolute_url, save_chat_image_bytes
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


async def load_studio_motion_render_bytes(
    session: AsyncSession,
    *,
    owner_id: int,
    render_id: int,
) -> tuple[bytes, str]:
    import httpx

    row = await session.get(StudioMotionRender, render_id)
    if not row or row.user_id != owner_id:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    url = (row.video_url or "").strip()
    if not url:
        raise HTTPException(status_code=404, detail="URL видео отсутствует")
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        r = await client.get(url)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Не удалось загрузить видео")
    ct = (r.headers.get("content-type") or "video/mp4").split(";")[0].strip()
    if not ct.startswith("video/"):
        ct = "video/mp4"
    return r.content, ct


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
        row = await session.get(StudioGeneration, studio_generation_id)
        if row and (row.content_type or "").startswith("video/"):
            raise HTTPException(
                status_code=400,
                detail="Для видео из архива используйте studio_motion_render_id",
            )
        return await load_studio_generation_image_bytes(
            session, owner_id=owner_id, generation_id=studio_generation_id
        )
    return None


async def resolve_outbound_video(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_motion_render_id: int | None,
) -> tuple[bytes, str] | None:
    if studio_motion_render_id is None or studio_motion_render_id <= 0:
        return None
    return await load_studio_motion_render_bytes(
        session, owner_id=owner_id, render_id=studio_motion_render_id
    )


async def send_telegram_outbound(
    *,
    token: str,
    chat_id: int,
    topic_id: int,
    text: str,
    image_bytes: bytes | None,
    image_mime: str | None,
    video_bytes: bytes | None = None,
    video_mime: str | None = None,
    reply_to_telegram_message_id: int | None = None,
) -> int | None:
    proxy = (settings.telegram_proxy or "").strip()
    session_aio = AiohttpSession(proxy=proxy) if proxy else None
    bot = Bot(token=token, session=session_aio) if session_aio else Bot(token=token)
    reply_kw: dict[str, int] = {}
    if reply_to_telegram_message_id is not None and reply_to_telegram_message_id > 0:
        reply_kw["reply_to_message_id"] = reply_to_telegram_message_id
    try:
        if video_bytes:
            ext = ".mp4"
            if video_mime and "webm" in video_mime:
                ext = ".webm"
            vid = BufferedInputFile(video_bytes, filename=f"video{ext}")
            if (text or "").strip():
                sent = await bot.send_video(
                    chat_id=chat_id,
                    video=vid,
                    caption=text,
                    direct_messages_topic_id=topic_id,
                    **reply_kw,
                )
            else:
                sent = await bot.send_video(
                    chat_id=chat_id,
                    video=vid,
                    direct_messages_topic_id=topic_id,
                    **reply_kw,
                )
        elif image_bytes:
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


async def _raw_telegram_set_message_reaction(
    *,
    token: str,
    chat_id: int,
    telegram_message_id: int,
    emoji: str | None,
    extra: dict[str, int],
) -> None:
    import httpx

    reaction_payload: list[dict[str, str]] = []
    if emoji and emoji.strip():
        reaction_payload = [{"type": "emoji", "emoji": emoji.strip()}]
    payload: dict = {
        "chat_id": chat_id,
        "message_id": telegram_message_id,
        "reaction": reaction_payload,
        **extra,
    }
    proxy = (settings.telegram_proxy or "").strip()
    async with httpx.AsyncClient(timeout=30.0, proxy=proxy or None) as client:
        r = await client.post(
            f"https://api.telegram.org/bot{token}/setMessageReaction",
            json=payload,
        )
    if r.status_code >= 400:
        raise RuntimeError(f"setMessageReaction {r.status_code}: {(r.text or '')[:300]}")


async def set_telegram_message_reaction(
    *,
    token: str,
    chat_id: int,
    telegram_message_id: int,
    emoji: str | None,
    topic_id: int | None = None,
) -> bool:
    """emoji=None или пустая строка — снять реакцию бота. True если Telegram принял."""
    tid = int(topic_id or 0)
    extras: list[dict[str, int]] = [{}]
    if tid > 0:
        extras = [
            {"direct_messages_topic_id": tid},
            {},
            {"message_thread_id": tid},
        ]

    for extra in extras:
        try:
            await _raw_telegram_set_message_reaction(
                token=token,
                chat_id=chat_id,
                telegram_message_id=telegram_message_id,
                emoji=emoji,
                extra=extra,
            )
            log.info(
                "setMessageReaction ok chat=%s msg=%s extra=%s emoji=%s",
                chat_id,
                telegram_message_id,
                extra or "plain",
                emoji or None,
            )
            return True
        except Exception as e:
            log.info(
                "setMessageReaction failed chat=%s msg=%s extra=%s: %s",
                chat_id,
                telegram_message_id,
                extra or "plain",
                e,
            )

    from aiogram.types import ReactionTypeEmoji

    proxy = (settings.telegram_proxy or "").strip()
    session_aio = AiohttpSession(proxy=proxy) if proxy else None
    bot = Bot(token=token, session=session_aio) if session_aio else Bot(token=token)
    reaction = [ReactionTypeEmoji(emoji=emoji.strip())] if emoji and emoji.strip() else []
    try:
        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=telegram_message_id,
            reaction=reaction,
        )
        return True
    except Exception as e:
        log.info(
            "setMessageReaction aiogram failed chat=%s msg=%s: %s",
            chat_id,
            telegram_message_id,
            e,
        )
    finally:
        await bot.session.close()
    return False


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
            from app.services.fanvue_peer_status import (
                fanvue_api_body_indicates_invalid_user,
                fanvue_peer_unavailable_http_exception,
            )

            if fanvue_api_body_indicates_invalid_user(e.body):
                raise fanvue_peer_unavailable_http_exception() from e
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
        from app.services.fanvue_peer_status import (
            fanvue_api_body_indicates_invalid_user,
            fanvue_peer_unavailable_http_exception,
        )

        if fanvue_api_body_indicates_invalid_user(e.body):
            raise fanvue_peer_unavailable_http_exception() from e
        st = e.status
        if st >= 500:
            st = 502
        elif st < 400:
            st = 502
        raise HTTPException(
            status_code=st,
            detail=(e.body or str(e))[:2000],
        ) from e


async def send_instagram_outbound(
    *,
    access_token: str,
    ig_user_id: str,
    recipient_id: str,
    owner_id: int,
    text: str,
    image_bytes: bytes | None,
    image_mime: str | None,
) -> str | None:
    image_url: str | None = None
    if image_bytes:
        base = (settings.public_app_url or "").strip().rstrip("/")
        if not base.lower().startswith("https://"):
            raise HTTPException(
                status_code=503,
                detail="Для отправки фото в Instagram нужен HTTPS PUBLIC_APP_URL",
            )
        rel, _mime = save_chat_image_bytes(
            owner_id=owner_id,
            raw=image_bytes,
            content_type=image_mime,
        )
        image_url = chat_media_public_absolute_url(owner_id=owner_id, relative_path=rel)

    if not (text or "").strip() and not image_url:
        raise HTTPException(status_code=400, detail="Пустое сообщение")

    try:
        return await send_instagram_message(
            access_token=access_token,
            ig_user_id=ig_user_id,
            recipient_id=recipient_id,
            text=text or "",
            image_url=image_url,
        )
    except InstagramAPIError as e:
        st = e.status if e.status >= 400 else 502
        detail = (e.body or str(e))[:2000]
        if "outside" in detail.lower() or "24 hour" in detail.lower():
            detail = (
                "Instagram: окно ответа 24 часа закрыто. "
                "Ответьте из приложения Instagram или дождитесь нового сообщения от пользователя."
            )
        raise HTTPException(status_code=st, detail=detail) from e
