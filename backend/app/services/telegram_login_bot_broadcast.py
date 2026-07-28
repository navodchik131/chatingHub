"""Рассылка сообщений через login-бот."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.connectors.telegram.login_bot.bot import create_login_bot
from app.db.models import TelegramLoginBotContact
from app.services.telegram_login_bot_contacts import list_reachable_login_bot_contact_ids

log = logging.getLogger(__name__)

SEND_DELAY_SECONDS = 0.05


@dataclass
class LoginBotBroadcastResult:
    total: int = 0
    sent: int = 0
    failed: int = 0
    blocked: int = 0
    errors: list[dict[str, str | int]] = field(default_factory=list)


async def _mark_blocked(session: AsyncSession, telegram_id: int) -> None:
    row = (
        await session.execute(
            select(TelegramLoginBotContact).where(
                TelegramLoginBotContact.telegram_id == telegram_id
            )
        )
    ).scalar_one_or_none()
    if row:
        row.blocked = True


async def send_login_bot_message(
    session: AsyncSession,
    *,
    telegram_id: int,
    text: str,
    parse_mode: str | None = "HTML",
    disable_web_page_preview: bool = False,
) -> None:
    if not settings.telegram_login_configured:
        raise RuntimeError("Login-бот не настроен")
    bot = create_login_bot()
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
    finally:
        await bot.session.close()


async def broadcast_login_bot_message(
    session: AsyncSession,
    *,
    text: str,
    parse_mode: str | None = "HTML",
    disable_web_page_preview: bool = False,
) -> LoginBotBroadcastResult:
    if not settings.telegram_login_configured:
        raise RuntimeError("Login-бот не настроен (TELEGRAM_LOGIN_BOT_TOKEN)")

    body = text.strip()
    if not body:
        raise ValueError("Текст сообщения обязателен")

    contact_ids = await list_reachable_login_bot_contact_ids(session)
    result = LoginBotBroadcastResult(total=len(contact_ids))

    if not contact_ids:
        return result

    bot = create_login_bot()
    try:
        for telegram_id in contact_ids:
            try:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=body,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
                result.sent += 1
            except TelegramForbiddenError:
                result.blocked += 1
                await _mark_blocked(session, telegram_id)
            except TelegramRetryAfter as e:
                await asyncio.sleep(float(e.retry_after) + 0.5)
                try:
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=body,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview,
                    )
                    result.sent += 1
                except TelegramForbiddenError:
                    result.blocked += 1
                    await _mark_blocked(session, telegram_id)
                except Exception as retry_err:
                    result.failed += 1
                    if len(result.errors) < 15:
                        result.errors.append(
                            {"telegram_id": telegram_id, "error": str(retry_err)}
                        )
            except Exception as e:
                result.failed += 1
                if len(result.errors) < 15:
                    result.errors.append({"telegram_id": telegram_id, "error": str(e)})
                log.warning("login bot broadcast failed tg=%s: %s", telegram_id, e)

            await asyncio.sleep(SEND_DELAY_SECONDS)
    finally:
        await bot.session.close()

    await session.commit()
    return result
