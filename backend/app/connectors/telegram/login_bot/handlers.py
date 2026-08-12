"""Login-бот: /start mm_* → завершение mobile auth."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from fastapi import HTTPException

from app.db.session import SessionLocal
from app.services.telegram_login_bot_contacts import upsert_login_bot_contact
from app.services.telegram_mobile_auth import (
    complete_mobile_auth_session,
    parse_mobile_auth_start_param,
    parse_mobile_link_start_param,
)

log = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    if not message.from_user:
        return

    tg_user = message.from_user
    try:
        async with SessionLocal() as session:
            await upsert_login_bot_contact(session, tg_user)
            await session.commit()
    except Exception:
        log.exception("login bot contact upsert failed tg=%s", tg_user.id)

    session_id = parse_mobile_link_start_param(command.args) or parse_mobile_auth_start_param(
        command.args
    )
    is_link = parse_mobile_link_start_param(command.args) is not None
    if not session_id:
        await message.answer(
            "Это бот входа в ModelMate.\n\n"
            "Откройте приложение ModelMate и нажмите «Войти через Telegram»."
        )
        return

    try:
        async with SessionLocal() as session:
            await complete_mobile_auth_session(
                session,
                session_id=session_id,
                telegram_id=tg_user.id,
                telegram_username=tg_user.username,
            )
            await session.commit()
    except HTTPException as e:
        detail = e.detail if isinstance(e.detail, str) else "Не удалось выполнить вход"
        await message.answer(f"❌ {detail}")
        return
    except Exception:
        log.exception("login bot mobile auth failed session=%s tg=%s", session_id, tg_user.id)
        await message.answer(
            "❌ Не удалось выполнить вход. Вернитесь в приложение и попробуйте снова."
        )
        return

    name = (tg_user.first_name or "").strip() or "друг"
    if is_link:
        await message.answer(
            f"✅ Готово, {name}!\n\n"
            "Telegram привязан к аккаунту. Вернитесь в кабинет ModelMate."
        )
        return
    await message.answer(
        f"✅ Готово, {name}!\n\n"
        "Вернитесь в приложение ModelMate — вход выполнен автоматически."
    )
