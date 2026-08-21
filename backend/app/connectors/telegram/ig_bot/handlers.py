"""Обработчики Instagram download Telegram-бота."""

from __future__ import annotations

import logging
import shutil

import anyio
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, InputMediaVideo, Message

from app.config import settings
from app.connectors.telegram.ig_bot.keyboards import (
    BTN_DOWNLOAD,
    BTN_HELP,
    BTN_LIMITS,
    BTN_MENU,
    MENU_BUTTONS,
    limit_exceeded_kb,
    limits_hint_short,
    limits_kb,
    main_menu_kb,
    reply_menu_kb,
)
from app.db.session import SessionLocal
from app.services.ig_bot.download import download_instagram_media
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
    "Привет! Я скачиваю **видео и фото из Instagram** по ссылке.\n\n"
    "Просто отправьте ссылку на Reels, пост или фото:\n"
    "`https://www.instagram.com/reel/…`\n"
    "`https://www.instagram.com/p/…`\n\n"
    + limits_hint_short()
)

_HELP = (
    "**Как пользоваться**\n\n"
    "1. Нажмите /start\n"
    "2. Отправьте ссылку на Reels, пост или фото (`/p/`, `/reel/`, `/reels/`)\n"
    "3. Получите файл(ы) в чат\n\n"
    "Поддерживаются **одиночные** ссылки: видео, фото и **карусели** (все слайды).\n"
    "Пачки и профили — в веб-приложении.\n\n"
    + limits_hint_short()
    + "\n\n"
    "Команды: /start /menu /limits /help"
)

_DOWNLOAD_HINT = (
    "Отправьте **ссылку** на Reels, пост, фото или карусель.\n\n"
    "Примеры:\n"
    "• `https://www.instagram.com/reel/ABC123/`\n"
    "• `https://www.instagram.com/p/XYZ789/`\n\n"
    "Карусель придёт альбомом со всеми фото/видео."
)


async def _send_main_menu(
    message: Message,
    *,
    text: str | None = None,
    parse_mode: str | None = None,
) -> None:
    await message.answer(
        text or "Выберите действие в меню или отправьте ссылку на Instagram:",
        parse_mode=parse_mode,
        reply_markup=reply_menu_kb(),
    )
    await message.answer("Быстрые кнопки:", reply_markup=main_menu_kb())


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
    await _send_main_menu(
        message,
        text=f"Привет, {name}!\n\n{_WELCOME}",
        parse_mode="Markdown",
    )


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


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await _send_main_menu(message)


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


@router.callback_query(F.data == "ig:menu:download")
async def cb_menu_download(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            _DOWNLOAD_HINT,
            parse_mode="Markdown",
            reply_markup=reply_menu_kb(),
        )


@router.callback_query(F.data == "ig:menu:main")
async def cb_menu_main(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await _send_main_menu(callback.message)


@router.message(F.text)
async def on_text(message: Message, bot: Bot) -> None:
    if not message.from_user or not message.text:
        return
    text = message.text.strip()
    if text in MENU_BUTTONS:
        if text == BTN_DOWNLOAD:
            await message.answer(_DOWNLOAD_HINT, parse_mode="Markdown", reply_markup=reply_menu_kb())
            return
        if text == BTN_LIMITS:
            await _send_limits(message, bot)
            return
        if text == BTN_HELP:
            await message.answer(_HELP, parse_mode="Markdown", reply_markup=reply_menu_kb())
            return
        if text == BTN_MENU:
            await _send_main_menu(message)
            return

    url = extract_instagram_url(text)
    if not url:
        if text.startswith("/"):
            return
        await message.answer(
            "Отправьте ссылку на Instagram Reels, пост или фото.\n"
            "Пример: https://www.instagram.com/reel/ABC123/\n\n"
            "Или нажмите «📥 Скачать» в меню.",
            reply_markup=reply_menu_kb(),
        )
        return

    status_msg = await message.answer("⏳ Скачиваю…")

    try:
        async with SessionLocal() as session:
            user = await get_or_create_ig_bot_user(session, message.from_user)
            try:
                await ensure_can_download(session, user, bot)
            except IgBotDailyLimitExceeded:
                status = await get_usage_status(session, user, bot)
                await session.commit()
                await status_msg.edit_text(
                    format_limit_exceeded_message(status),
                    parse_mode="HTML",
                    reply_markup=limit_exceeded_kb(channel_url=status.channel_url),
                )
                return
            user_id = user.id
            await session.commit()

        media = await anyio.to_thread.run_sync(download_instagram_media, url)
        tmp_dir = media.temp_dir
        try:
            max_bytes = int(settings.ig_bot_max_video_bytes)
            oversized = [it for it in media.items if it.path.stat().st_size > max_bytes]
            if oversized and len(media.items) == 1:
                size = oversized[0].path.stat().st_size
                mb = size / (1024 * 1024)
                cap = max_bytes / (1024 * 1024)
                await status_msg.edit_text(
                    f"Файл слишком большой для Telegram ({mb:.1f} МБ, лимит {cap:.0f} МБ).\n"
                    "Попробуйте другой пост или скачайте через веб-приложение."
                )
                return

            sendable = [it for it in media.items if it.path.stat().st_size <= max_bytes]
            if not sendable:
                await status_msg.edit_text(
                    "Все файлы в посте слишком большие для Telegram."
                )
                return

            n = len(sendable)
            if n == 1:
                label = "фото" if sendable[0].kind == "image" else "видео"
            else:
                label = f"карусель ({n})"
            await status_msg.edit_text(f"📤 Отправляю {label}…")
            usage_note = ""
            try:
                async with SessionLocal() as session:
                    used = await record_successful_download(session, user_id=user_id)
                    user = await get_or_create_ig_bot_user(session, message.from_user)
                    usage = await get_usage_status(session, user, bot)
                    await session.commit()
                usage_note = f"\n\nСегодня: {used}/{usage.limit}"
            except Exception:
                log.exception(
                    "ig bot failed to record daily limit user_id=%s telegram_id=%s",
                    user_id,
                    message.from_user.id,
                )

            caption = f"{url}{usage_note}"
            if len(sendable) == 1:
                it = sendable[0]
                file = FSInputFile(str(it.path), filename=it.filename)
                if it.kind == "image":
                    try:
                        await message.answer_photo(file, caption=caption)
                    except Exception:
                        await message.answer_document(file, caption=caption)
                else:
                    await message.answer_video(file, caption=caption)
            else:
                # Telegram media group: максимум 10 за раз.
                for chunk_i in range(0, len(sendable), 10):
                    chunk = sendable[chunk_i : chunk_i + 10]
                    group = []
                    for j, it in enumerate(chunk):
                        file = FSInputFile(str(it.path), filename=it.filename)
                        cap = caption if chunk_i == 0 and j == 0 else None
                        if it.kind == "image":
                            group.append(InputMediaPhoto(media=file, caption=cap))
                        else:
                            group.append(InputMediaVideo(media=file, caption=cap))
                    await message.answer_media_group(group)

            await status_msg.delete()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    except RuntimeError as e:
        log.warning("ig bot download failed user=%s url=%s: %s", message.from_user.id, url, e)
        await status_msg.edit_text(str(e))
    except Exception:
        log.exception("ig bot unexpected error user=%s", message.from_user.id)
        await status_msg.edit_text("Не удалось скачать. Попробуйте позже.")
