"""Обработчики Instagram download Telegram-бота."""

from __future__ import annotations

import logging
import shutil

import anyio
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.config import settings
from app.connectors.telegram.ig_bot.keyboards import (
    limit_exceeded_kb,
    limits_hint_short,
    limits_kb,
    main_menu_kb,
)
from app.db.session import SessionLocal
from app.services.ig_bot.download import download_instagram_video
from app.services.ig_bot.limits import (
    IgBotDailyLimitExceeded,
    ensure_can_download,
    format_limit_exceeded_message,
    format_usage_message,
    get_usage_status,
    record_successful_download,
)
from app.services.ig_bot.repo import get_or_create_ig_bot_user
from app.services.ig_bot.urls import extract_instagram_url

log = logging.getLogger(__name__)

router = Router(name="ig_bot")

_WELCOME = (
    "Привет! Я скачиваю **видео из Instagram** по ссылке.\n\n"
    "Просто отправьте ссылку на Reels или пост с видео:\n"
    "`https://www.instagram.com/reel/…`\n\n"
    + limits_hint_short()
)

_HELP = (
    "**Как пользоваться**\n\n"
    "1. Нажмите /start\n"
    "2. Отправьте ссылку на Reels или пост (`/p/`, `/reel/`, `/reels/`)\n"
    "3. Получите видео файлом в чат\n\n"
    "Поддерживаются только **одиночные** ссылки на видео.\n"
    "Пачки и профили — в веб-приложении.\n\n"
    + limits_hint_short()
    + "\n\n"
    "Команды: /start /limits /help"
)


async def _send_main_menu(message: Message, *, text: str | None = None) -> None:
    await message.answer(text or "Главное меню:", reply_markup=main_menu_kb())


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not message.from_user:
        return
    try:
        async with SessionLocal() as session:
            await get_or_create_ig_bot_user(session, message.from_user)
            await session.commit()
    except Exception:
        log.exception("ig bot /start failed telegram_id=%s", message.from_user.id)
        await message.answer("Не удалось зарегистрировать вас. Попробуйте позже.")
        return
    name = message.from_user.first_name or "друг"
    await message.answer(f"Привет, {name}!\n\n{_WELCOME}", parse_mode="Markdown")
    await _send_main_menu(message)


async def _send_limits(message: Message, bot: Bot) -> None:
    if not message.from_user:
        return
    async with SessionLocal() as session:
        user = await get_or_create_ig_bot_user(session, message.from_user)
        status = await get_usage_status(session, user, bot)
        await session.commit()
    await message.answer(
        format_usage_message(status),
        parse_mode="HTML",
        reply_markup=limits_kb(channel_url=status.channel_url),
    )


@router.message(Command("limits"))
async def cmd_limits(message: Message, bot: Bot) -> None:
    await _send_limits(message, bot)


@router.callback_query(F.data == "ig:menu:limits")
async def cb_menu_limits(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    if callback.message:
        await _send_limits(callback.message, bot)


@router.callback_query(F.data == "ig:check_sub")
async def cb_check_subscription(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not callback.message:
        return
    async with SessionLocal() as session:
        user = await get_or_create_ig_bot_user(session, callback.from_user)
        status = await get_usage_status(session, user, bot)
        await session.commit()
    await callback.answer("Проверено")
    text = format_usage_message(status)
    if status.subscribed:
        text += "\n\n✅ Подписка подтверждена — повышенный лимит активен."
    else:
        text += "\n\n❌ Подписка не найдена. Подпишитесь на канал и нажмите снова."
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=limits_kb(channel_url=status.channel_url),
    )


@router.message(Command("help"))
@router.callback_query(F.data == "ig:menu:help")
async def cmd_help(event: Message | CallbackQuery) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(_HELP, parse_mode="Markdown")
        return
    await event.answer(_HELP, parse_mode="Markdown")


@router.callback_query(F.data == "ig:menu:main")
async def cb_menu_main(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await _send_main_menu(callback.message)


@router.message(F.text)
async def on_text(message: Message, bot: Bot) -> None:
    if not message.from_user or not message.text:
        return
    url = extract_instagram_url(message.text)
    if not url:
        if message.text.strip().startswith("/"):
            return
        await message.answer(
            "Отправьте ссылку на Instagram Reels или пост с видео.\n"
            "Пример: https://www.instagram.com/reel/ABC123/",
            reply_markup=main_menu_kb(),
        )
        return

    status_msg = await message.answer("⏳ Скачиваю видео…")

    try:
        async with SessionLocal() as session:
            user = await get_or_create_ig_bot_user(session, message.from_user)
            try:
                status = await ensure_can_download(session, user, bot)
            except IgBotDailyLimitExceeded:
                status = await get_usage_status(session, user, bot)
                await session.commit()
                await status_msg.edit_text(
                    format_limit_exceeded_message(status),
                    parse_mode="HTML",
                    reply_markup=limit_exceeded_kb(channel_url=status.channel_url),
                )
                return
            await session.commit()

        file_path, tmp_dir, filename = await anyio.to_thread.run_sync(
            download_instagram_video, url
        )
        try:
            size = file_path.stat().st_size
            max_bytes = int(settings.ig_bot_max_video_bytes)
            if size > max_bytes:
                mb = size / (1024 * 1024)
                cap = max_bytes / (1024 * 1024)
                await status_msg.edit_text(
                    f"Видео слишком большое для Telegram ({mb:.1f} МБ, лимит {cap:.0f} МБ).\n"
                    "Попробуйте другой ролик или скачайте через веб-приложение."
                )
                return

            await status_msg.edit_text("📤 Отправляю видео…")
            video = FSInputFile(str(file_path), filename=filename)
            await message.answer_video(video, caption=url)

            async with SessionLocal() as session:
                user = await get_or_create_ig_bot_user(session, message.from_user)
                await record_successful_download(session, user_id=user.id)
                await session.commit()

            await status_msg.delete()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    except RuntimeError as e:
        log.warning("ig bot download failed user=%s url=%s: %s", message.from_user.id, url, e)
        await status_msg.edit_text(str(e))
    except Exception:
        log.exception("ig bot unexpected error user=%s", message.from_user.id)
        await status_msg.edit_text("Не удалось скачать видео. Попробуйте позже.")
