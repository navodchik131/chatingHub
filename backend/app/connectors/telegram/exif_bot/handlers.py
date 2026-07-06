"""Обработчики EXIF Telegram-бота."""

from __future__ import annotations

import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.connectors.telegram.exif_bot.keyboards import (
    camera_pick_kb,
    cancel_kb,
    geo_kb,
    location_reply_kb,
    main_menu_kb,
    preset_picker_kb,
    profiles_list_kb,
    remove_reply_kb,
    skip_main_kb,
)
from app.connectors.telegram.exif_bot.media import download_image_from_message, file_hint_markdown
from app.connectors.telegram.exif_bot.states import ExifBotStates
from app.db.session import SessionLocal
from app.services.exif_bot.process import (
    extract_reference_profile,
    guess_selfie_from_image,
    process_image,
    profile_is_ready,
)
from app.services.exif_bot.repo import (
    create_profile,
    delete_profile,
    get_or_create_exif_bot_user,
    get_profile_for_user,
    list_profiles,
)
from app.services.studio_exif_profile import phone_exif_profile_from_json, phone_exif_profile_summary

log = logging.getLogger(__name__)

router = Router(name="exif_bot")

_WELCOME = (
    "Привет! Я подставляю EXIF с вашего телефона в фото — как в студии ModelMate.\n\n"
    "1️⃣ Создайте **профиль** (модель телефона + эталоны с камеры + GPS)\n"
    "2️⃣ Отправьте фото **файлом** — получите обработанный JPEG\n\n"
    + file_hint_markdown()
)

_HELP = (
    "**Как пользоваться**\n\n"
    "• Эталоны — только **файлом** из галереи телефона (JPEG/HEIC, не пересылка из чата).\n"
    "• Сначала селфи с **фронталки**, потом с **основной** камеры.\n"
    "• Гео — кнопка «Отправить геолокацию» или `широта, долгота`.\n"
    "• Обработка: файл → выбор профиля → камера → готовый JPEG.\n\n"
    "Команды: /start /profiles /help /cancel"
)


def _parse_geo(text: str) -> tuple[float, float] | None:
    cleaned = text.strip().replace(";", ",")
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if len(parts) != 2:
        return None
    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


async def _send_main_menu(message: Message, *, text: str | None = None) -> None:
    await message.answer(text or "Главное меню:", reply_markup=main_menu_kb())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not message.from_user:
        return
    async with SessionLocal() as session:
        await get_or_create_exif_bot_user(session, message.from_user)
        await session.commit()
    name = message.from_user.first_name or "друг"
    await message.answer(f"Привет, {name}!\n\n{_WELCOME}", parse_mode="Markdown")
    await _send_main_menu(message)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(_HELP, parse_mode="Markdown")


@router.message(Command("cancel"))
@router.callback_query(F.data == "exif:cancel")
async def cmd_cancel(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(event, CallbackQuery):
        await event.answer("Отменено")
        if event.message:
            await event.message.answer("Отменено.", reply_markup=remove_reply_kb())
            await _send_main_menu(event.message)
        return
    await event.answer("Отменено.", reply_markup=remove_reply_kb())
    await _send_main_menu(event)


@router.message(Command("profiles"))
async def cmd_profiles(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not message.from_user:
        return
    async with SessionLocal() as session:
        user = await get_or_create_exif_bot_user(session, message.from_user)
        profiles = await list_profiles(session, user.id)
        await session.commit()
    if not profiles:
        await message.answer("Профилей пока нет. Нажмите «Создать профиль».", reply_markup=main_menu_kb())
        return
    lines = ["**Ваши профили:**"]
    for p in profiles:
        selfie = phone_exif_profile_summary(phone_exif_profile_from_json(p.phone_exif_selfie_json))
        main = phone_exif_profile_summary(phone_exif_profile_from_json(p.phone_exif_main_json))
        geo = "✓ GPS" if p.export_lat is not None else "без GPS"
        lines.append(f"• *{p.title}* — {geo}\n  selfie: {selfie or '—'}\n  main: {main or '—'}")
    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=profiles_list_kb(profiles, action="manage"))


@router.callback_query(F.data == "exif:menu:home")
async def cb_menu_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message:
        await _send_main_menu(callback.message)


@router.callback_query(F.data == "exif:menu:help")
async def cb_menu_help(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(_HELP, parse_mode="Markdown")


@router.callback_query(F.data == "exif:menu:profiles")
async def cb_menu_profiles(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    async with SessionLocal() as session:
        user = await get_or_create_exif_bot_user(session, callback.from_user)
        profiles = await list_profiles(session, user.id)
        await session.commit()
    if not profiles:
        await callback.message.answer("Профилей нет. Создайте первый.", reply_markup=main_menu_kb())
        return
    await callback.message.answer(
        "Управление профилями:",
        reply_markup=profiles_list_kb(profiles, action="manage"),
    )


@router.callback_query(F.data.startswith("exif:del:"))
async def cb_delete_profile(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        return
    pid = int(callback.data.split(":")[-1])
    async with SessionLocal() as session:
        user = await get_or_create_exif_bot_user(session, callback.from_user)
        ok = await delete_profile(session, user_id=user.id, profile_id=pid)
        profiles = await list_profiles(session, user.id)
        await session.commit()
    await callback.answer("Удалено" if ok else "Не найден")
    if not profiles:
        await callback.message.answer("Профилей больше нет.", reply_markup=main_menu_kb())
        return
    await callback.message.answer(
        "Профили:",
        reply_markup=profiles_list_kb(profiles, action="manage"),
    )


@router.callback_query(F.data == "exif:menu:create")
async def cb_menu_create(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return
    await state.set_state(ExifBotStates.create_name)
    await state.update_data(
        draft_selfie_json=None,
        draft_main_json=None,
        draft_preset_id=None,
    )
    await callback.message.answer(
        "Как назвать профиль? (например: «Мой iPhone 15»)\n\n/cancel — отмена",
        reply_markup=cancel_kb(),
    )


@router.message(ExifBotStates.create_name, F.text)
async def create_name(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title or title.startswith("/"):
        await message.answer("Введите название текстом.")
        return
    if len(title) > 120:
        await message.answer("Слишком длинное название (макс. 120 символов).")
        return
    await state.update_data(draft_title=title)
    await state.set_state(ExifBotStates.create_preset)
    await message.answer(
        f"Профиль «{title}». Выберите модель телефона (базовый пресет):",
        reply_markup=preset_picker_kb(0),
    )


@router.callback_query(F.data.startswith("exif:preset_page:"))
async def cb_preset_page(callback: CallbackQuery, state: FSMContext) -> None:
    page = int(callback.data.split(":")[-1])
    await callback.answer()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=preset_picker_kb(page))


@router.callback_query(ExifBotStates.create_preset, F.data.startswith("exif:preset:"))
async def cb_pick_preset(callback: CallbackQuery, state: FSMContext) -> None:
    preset_id = callback.data.split(":")[-1]
    await state.update_data(draft_preset_id=preset_id)
    await state.set_state(ExifBotStates.create_selfie)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Шаг 1/3 — **эталон с фронталки**.\n\n"
            + file_hint_markdown()
            + "\n\nОтправьте JPEG или HEIC **файлом** с фронтальной камеры.",
            parse_mode="Markdown",
            reply_markup=cancel_kb(),
        )


def _reference_filename(message: Message) -> str | None:
    if message.document and message.document.file_name:
        return message.document.file_name.strip() or None
    return None


@router.message(ExifBotStates.create_selfie, F.document | F.photo)
async def create_selfie_ref(message: Message, state: FSMContext, bot: Bot) -> None:
    try:
        data, is_doc = await download_image_from_message(message, bot)
        blob, summary = extract_reference_profile(data, filename=_reference_filename(message))
    except ValueError as e:
        await message.answer(str(e), parse_mode="Markdown")
        return
    warn = ""
    if not is_doc:
        warn = "\n\n⚠️ Вы отправили сжатое фото — EXIF мог быть повреждён. Лучше файлом."
    await state.update_data(draft_selfie_json=blob)
    await state.set_state(ExifBotStates.create_main)
    await message.answer(
        f"Фронталка сохранена: {summary}{warn}\n\n"
        "Шаг 2/3 — **эталон с основной камеры** (файлом).",
        parse_mode="Markdown",
        reply_markup=skip_main_kb(),
    )


@router.callback_query(ExifBotStates.create_main, F.data == "exif:main:skip")
async def skip_main_ref(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(draft_main_json=None)
    await state.set_state(ExifBotStates.create_geo)
    if callback.message:
        await callback.message.answer(
            "Шаг 3/3 — **геолокация** для GPS в EXIF.\n"
            "Отправьте 📍 или координаты `55.7558, 37.6173`, либо «Без GPS».",
            parse_mode="Markdown",
            reply_markup=geo_kb(),
        )
        await callback.message.answer(
            "Или нажмите кнопку ниже:",
            reply_markup=location_reply_kb(),
        )


@router.message(ExifBotStates.create_main, F.document | F.photo)
async def create_main_ref(message: Message, state: FSMContext, bot: Bot) -> None:
    try:
        data, is_doc = await download_image_from_message(message, bot)
        blob, summary = extract_reference_profile(data, filename=_reference_filename(message))
    except ValueError as e:
        await message.answer(str(e), parse_mode="Markdown")
        return
    warn = ""
    if not is_doc:
        warn = "\n\n⚠️ Лучше отправлять файлом."
    await state.update_data(draft_main_json=blob)
    await state.set_state(ExifBotStates.create_geo)
    await message.answer(
        f"Основная камера: {summary}{warn}\n\n"
        "Шаг 3/3 — **геолокация**.",
        parse_mode="Markdown",
        reply_markup=geo_kb(),
    )
    await message.answer("Или кнопка:", reply_markup=location_reply_kb())


@router.callback_query(ExifBotStates.create_geo, F.data == "exif:geo:skip")
async def geo_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _finish_profile_create(callback.message, state, callback.from_user, lat=None, lon=None)


@router.message(ExifBotStates.create_geo, F.location)
async def create_geo_location(message: Message, state: FSMContext) -> None:
    loc = message.location
    if not loc:
        return
    await _finish_profile_create(
        message, state, message.from_user, lat=loc.latitude, lon=loc.longitude
    )


@router.message(ExifBotStates.create_geo, F.text)
async def create_geo_text(message: Message, state: FSMContext) -> None:
    parsed = _parse_geo(message.text or "")
    if not parsed:
        await message.answer(
            "Не понял координаты. Формат: `55.7558, 37.6173` или кнопка геолокации.",
            parse_mode="Markdown",
        )
        return
    lat, lon = parsed
    await _finish_profile_create(message, state, message.from_user, lat=lat, lon=lon)


async def _finish_profile_create(
    message: Message | None,
    state: FSMContext,
    from_user,
    *,
    lat: float | None,
    lon: float | None,
) -> None:
    if not message or not from_user:
        return
    data = await state.get_data()
    title = data.get("draft_title") or "Профиль"
    try:
        async with SessionLocal() as session:
            user = await get_or_create_exif_bot_user(session, from_user)
            profile = await create_profile(
                session,
                user_id=user.id,
                title=title,
                camera_preset_id=data.get("draft_preset_id"),
                phone_exif_selfie_json=data.get("draft_selfie_json"),
                phone_exif_main_json=data.get("draft_main_json"),
                export_lat=lat,
                export_lon=lon,
            )
            await session.commit()
            pid = profile.id
    except ValueError as e:
        await message.answer(str(e), reply_markup=main_menu_kb())
        await state.clear()
        return
    await state.clear()
    geo_txt = f"GPS: {lat:.5f}, {lon:.5f}" if lat is not None else "GPS: выключен"
    await message.answer(
        f"✅ Профиль «{title}» создан (#{pid}).\n{geo_txt}\n\n"
        "Теперь можно обработать фото.",
        reply_markup=remove_reply_kb(),
    )
    await _send_main_menu(message)


@router.callback_query(F.data == "exif:menu:process")
async def cb_menu_process(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    async with SessionLocal() as session:
        user = await get_or_create_exif_bot_user(session, callback.from_user)
        profiles = await list_profiles(session, user.id)
        await session.commit()
    ready = [p for p in profiles if profile_is_ready(p)]
    if not ready:
        await callback.message.answer(
            "Сначала создайте профиль с эталонами или пресетом.",
            reply_markup=main_menu_kb(),
        )
        return
    await state.set_state(ExifBotStates.waiting_photo)
    await callback.message.answer(
        "Отправьте изображение **файлом** для обработки.\n\n" + file_hint_markdown(),
        parse_mode="Markdown",
        reply_markup=cancel_kb(),
    )


@router.message(ExifBotStates.waiting_photo, F.document | F.photo)
async def process_incoming_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.from_user:
        return
    try:
        data, is_doc = await download_image_from_message(message, bot)
    except ValueError as e:
        await message.answer(str(e), parse_mode="Markdown")
        return
    await state.update_data(pending_image=data, pending_is_doc=is_doc)
    async with SessionLocal() as session:
        user = await get_or_create_exif_bot_user(session, message.from_user)
        profiles = [p for p in await list_profiles(session, user.id) if profile_is_ready(p)]
        await session.commit()
    if not profiles:
        await state.clear()
        await message.answer("Нет готовых профилей.", reply_markup=main_menu_kb())
        return
    warn = ""
    if not is_doc:
        warn = "\n⚠️ Фото сжато Telegram — EXIF исходника уже потерян, но метаданные телефона подставим.\n"
    await message.answer(
        f"{warn}Выберите профиль:",
        reply_markup=profiles_list_kb(profiles, action="pick"),
    )


@router.callback_query(F.data.startswith("exif:pick:"))
async def cb_pick_profile(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("pending_image"):
        await callback.answer("Сначала отправьте фото", show_alert=True)
        return
    pid = int(callback.data.split(":")[-1])
    await state.update_data(pending_profile_id=pid)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Какую камеру эмулировать?",
            reply_markup=camera_pick_kb(pid),
        )


@router.callback_query(F.data.startswith("exif:camera:"))
async def cb_pick_camera(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not callback.from_user or not callback.message:
        return
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Ошибка")
        return
    profile_id = int(parts[2])
    mode = parts[3]
    fsm = await state.get_data()
    image_bytes = fsm.get("pending_image")
    if not image_bytes:
        await callback.answer("Фото не найдено — отправьте снова", show_alert=True)
        await state.clear()
        return

    async with SessionLocal() as session:
        user = await get_or_create_exif_bot_user(session, callback.from_user)
        profile = await get_profile_for_user(
            session, user_id=user.id, profile_id=profile_id
        )
        await session.commit()

    if not profile:
        await callback.answer("Профиль не найден", show_alert=True)
        return

    if mode == "auto":
        selfie = guess_selfie_from_image(image_bytes)
    else:
        selfie = mode == "selfie"

    await callback.answer("Обрабатываю…")
    status = await callback.message.answer("⏳ Обработка…")

    try:
        out = await process_image(image_bytes, profile, selfie=selfie)
    except ValueError as e:
        await status.edit_text(f"❌ {e}")
        return
    except Exception:
        log.exception("exif bot process failed profile=%s", profile_id)
        await status.edit_text("❌ Ошибка обработки. Попробуйте другой файл.")
        return

    cam_label = "selfie" if selfie else "main"
    fname = re.sub(r"[^\w\-]+", "_", profile.title or "photo")[:40] + "_exif.jpg"
    doc = BufferedInputFile(out, filename=fname)
    await status.delete()
    await callback.message.answer_document(
        doc,
        caption=f"✅ {profile.title} · {cam_label}",
    )
    await state.clear()
    await callback.message.answer("Готово!", reply_markup=main_menu_kb())


@router.message(F.document | F.photo)
async def fallback_photo(message: Message, state: FSMContext) -> None:
    """Фото вне сценария — подсказка."""
    current = await state.get_state()
    if current:
        return
    await message.answer(
        "Чтобы обработать фото, нажмите «📷 Обработать фото» в меню.\n\n/start — главное меню",
        reply_markup=main_menu_kb(),
    )
