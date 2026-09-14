"""Отправка paid media от имени OWNER (business_connection_id)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputPaidMediaPhoto, InputPaidMediaVideo
from aiogram.types import FSInputFile

from app.connectors.telegram.stars_business.media_storage import decode_media_paths
from app.connectors.telegram.stars_business.paths import absolute_media_path
from app.db.models import StarsBusinessConnection, StarsBusinessOrder

log = logging.getLogger(__name__)


@dataclass
class SendPaidResult:
    ok: bool
    message_id: int | None = None
    error_code: str | None = None
    error_text: str | None = None


def _map_telegram_error(exc: TelegramBadRequest) -> tuple[str, str]:
    text = str(exc.message or exc).upper()
    if "BUSINESS_CHAT_INACTIVE" in text:
        return (
            "BUSINESS_CHAT_INACTIVE",
            "У фана нет входящих за последние 24 часа — Telegram не даст отправить paid media. "
            "Попросите фана написать OWNER или дождитесь нового сообщения.",
        )
    if "BUSINESS_CONNECTION_NOT_ALLOWED" in text:
        return (
            "BUSINESS_CONNECTION_NOT_ALLOWED",
            "Secretary Mode выключен в @BotFather или бот не подключён к Business OWNER.",
        )
    return ("TELEGRAM_BAD_REQUEST", str(exc.message or exc)[:500])


async def send_paid_media_order(
    bot: Bot,
    *,
    conn: StarsBusinessConnection,
    order: StarsBusinessOrder,
) -> SendPaidResult:
    try:
        rel_paths = decode_media_paths(order.media_relative_path)
    except ValueError:
        return SendPaidResult(ok=False, error_code="MEDIA_INVALID", error_text="Некорректный список медиа в заказе.")

    abs_paths = [absolute_media_path(rel) for rel in rel_paths]
    if not all(p.is_file() for p in abs_paths):
        return SendPaidResult(ok=False, error_code="MEDIA_MISSING", error_text="Файл медиа не найден на сервере.")

    star_count = max(1, min(25_000, int(order.star_count)))
    payload = str(order.id)
    caption = (order.caption or "").strip() or None

    if order.media_type == "video":
        if len(abs_paths) != 1:
            return SendPaidResult(
                ok=False,
                error_code="MEDIA_INVALID",
                error_text="В paid media только одно видео за раз.",
            )
        media = [InputPaidMediaVideo(media=FSInputFile(abs_paths[0]))]
    else:
        media = [InputPaidMediaPhoto(media=FSInputFile(p)) for p in abs_paths[:10]]

    try:
        msg = await bot.send_paid_media(
            chat_id=int(order.fan_chat_id),
            star_count=star_count,
            media=media,
            business_connection_id=conn.connection_id,
            caption=caption,
            protect_content=True,
            payload=payload,
        )
        return SendPaidResult(ok=True, message_id=int(msg.message_id))
    except TelegramBadRequest as e:
        code, human = _map_telegram_error(e)
        log.warning(
            "stars business send_paid_media failed order=%s code=%s",
            order.id,
            code,
        )
        return SendPaidResult(ok=False, error_code=code, error_text=human)
    except Exception as e:
        log.exception("stars business send_paid_media unexpected order=%s", order.id)
        return SendPaidResult(ok=False, error_code="SEND_FAILED", error_text=str(e)[:500])
