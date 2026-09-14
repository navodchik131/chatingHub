"""OPERATOR: wizard paid media в личке с ботом."""

from __future__ import annotations

import asyncio
import logging
import uuid

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.connectors.telegram.stars_business.fan_window import chat_window_open
from app.connectors.telegram.stars_business.forward import fan_chat_id_from_forward
from app.connectors.telegram.stars_business.keyboards import (
    OPERATOR_BTN_CANCEL,
    OPERATOR_BTN_CHATS,
    OPERATOR_BTN_PAID,
    confirm_send_kb,
    fan_pick_kb,
    format_fan_list,
    operator_main_kb,
    operator_menu_reply_kb,
)
from app.connectors.telegram.stars_business.media_storage import encode_media_paths
from app.connectors.telegram.stars_business.paths import owner_media_dir, relative_media_path
from app.connectors.telegram.stars_business.repo import (
    create_order,
    get_active_connection,
    is_operator,
    is_owner,
    list_fan_chats,
    mark_order_failed,
    mark_order_sent,
)
from app.connectors.telegram.stars_business.send import send_paid_media_order
from app.connectors.telegram.stars_business.states import OperatorPaidStates
from app.db.session import SessionLocal

log = logging.getLogger(__name__)

# Сбор альбома (media_group): Telegram шлёт каждое фото отдельным апдейтом.
_ALBUM_COLLECT_SEC = 1.25
_MAX_ALBUM_PHOTOS = 10
_album_finalize_tasks: dict[tuple[int, str], asyncio.Task[None]] = {}

router = Router(name="stars_business_operator")
router.message.filter(F.chat.type == "private")


async def _resolve_access(telegram_user_id: int) -> tuple[str, int | None]:
    """Роль и owner_tg_user_id (этап 1 — один OWNER)."""
    async with SessionLocal() as session:
        conn = await get_active_connection(session)
        if conn is None:
            return "no_business", None
        if not conn.is_enabled:
            return "business_off", None
        owner_id = int(conn.owner_tg_user_id)
        if await is_owner(session, owner_id, telegram_user_id):
            return "OWNER", owner_id
        if await is_operator(session, owner_tg_user_id=owner_id, telegram_user_id=telegram_user_id):
            return "OPERATOR", owner_id
    return "denied", None


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    uid = message.from_user.id if message.from_user else 0
    role, owner_id = await _resolve_access(uid)
    if role == "OWNER":
        await message.answer(
            "Вы <b>OWNER</b>. Business-подключение активно.\n"
            "OPERATOR работает через /paid — доступ только по whitelist.",
            parse_mode="HTML",
        )
        return
    if role == "OPERATOR":
        await message.answer(
            "Вы <b>OPERATOR</b>. Отправка paid media от имени OWNER.\n"
            "Меню внизу или кнопки под сообщением.",
            parse_mode="HTML",
            reply_markup=operator_menu_reply_kb(),
        )
        await message.answer("Быстрые действия:", reply_markup=operator_main_kb())
        return
    if role == "no_business":
        await message.answer(
            "Business-подключение ещё <b>не зарегистрировано</b> на сервере.\n\n"
            "<b>OWNER</b> (аккаунт Telegram Business): Настройки → Business → "
            "<b>Chatbots</b> → подключите <b>этого</b> бота (Secretary Mode в BotFather).\n\n"
            "После подключения OWNER увидит «Вы OWNER», OPERATOR из whitelist — /start снова.",
            parse_mode="HTML",
        )
        return
    if role == "business_off":
        await message.answer(
            "Business-подключение отключено в Telegram.\n"
            "OWNER: снова включите бота в Business → Chatbots.",
        )
        return
    await message.answer(
        "Нет доступа. Ваш Telegram id не в whitelist OPERATOR — попросите OWNER добавить "
        "STARS_BUSINESS_OPERATOR_TELEGRAM_IDS на сервере."
    )


@router.message(F.text.in_({OPERATOR_BTN_PAID, OPERATOR_BTN_CHATS, OPERATOR_BTN_CANCEL}))
async def operator_menu_text(message: Message, state: FSMContext) -> None:
    """Нижнее меню OPERATOR — те же действия, что /paid /chats /cancel."""
    text = (message.text or "").strip()
    if text == OPERATOR_BTN_PAID:
        await cmd_paid(message, state)
    elif text == OPERATOR_BTN_CHATS:
        await cmd_chats(message)
    elif text == OPERATOR_BTN_CANCEL:
        await cmd_cancel(message, state)


@router.message(Command("cancel"))
@router.callback_query(F.data == "sb:cancel")
async def cmd_cancel(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text = "Отменено."
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(text, reply_markup=operator_menu_reply_kb())
    else:
        uid = event.from_user.id if event.from_user else 0
        role, _ = await _resolve_access(uid)
        kb = operator_menu_reply_kb() if role == "OPERATOR" else None
        await event.answer(text, reply_markup=kb)


@router.message(Command("chats"))
@router.callback_query(F.data == "sb:chats")
async def cmd_chats(event: Message | CallbackQuery) -> None:
    uid = event.from_user.id if event.from_user else 0
    role, owner_id = await _resolve_access(uid)
    if role != "OPERATOR" or owner_id is None:
        if isinstance(event, CallbackQuery):
            await event.answer("Нет доступа", show_alert=True)
        else:
            await event.answer("Нет доступа.")
        return
    async with SessionLocal() as session:
        conn = await get_active_connection(session)
        chats = await list_fan_chats(session, owner_id)
    text = format_fan_list(chats, owner_linked=conn is not None and conn.is_enabled)
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(text, parse_mode="HTML")
    else:
        await event.answer(text, parse_mode="HTML")


@router.message(Command("paid"))
@router.callback_query(F.data == "sb:paid")
async def cmd_paid(event: Message | CallbackQuery, state: FSMContext) -> None:
    uid = event.from_user.id if event.from_user else 0
    role, owner_id = await _resolve_access(uid)
    if role != "OPERATOR" or owner_id is None:
        if isinstance(event, CallbackQuery):
            await event.answer("Нет доступа", show_alert=True)
        else:
            await event.answer("Нет доступа.")
        return
    async with SessionLocal() as session:
        conn = await get_active_connection(session)
        if not conn:
            msg = "OWNER ещё не подключил бота в Telegram Business (Secretary Mode)."
            if isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            else:
                await event.answer(msg)
            return
    await state.set_state(OperatorPaidStates.waiting_media)
    await state.update_data(owner_tg_user_id=owner_id, operator_tg_user_id=uid)
    prompt = (
        "Шаг 1/3: отправьте <b>фото или видео</b>.\n"
        "Можно <b>альбом</b> (несколько фото одной группой, до 10) — соберём автоматически.\n"
        "Видео — только одним файлом.\n"
        f"{OPERATOR_BTN_CANCEL} — отмена."
    )
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(prompt, parse_mode="HTML")
    else:
        await event.answer(prompt, parse_mode="HTML")


async def _download_message_media(message: Message, bot: Bot, owner_id: int) -> tuple[str, str]:
    """Скачать фото/видео в каталог OWNER; вернуть (relative_path, media_type)."""
    media_type = "video" if message.video else "photo"
    ext = "mp4" if media_type == "video" else "jpg"
    fname = f"{uuid.uuid4().hex}.{ext}"
    dest = owner_media_dir(owner_id) / fname
    if message.video:
        file = await bot.get_file(message.video.file_id)
        await bot.download_file(file.file_path, dest)
    else:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        await bot.download_file(file.file_path, dest)
    return relative_media_path(owner_id, fname), media_type


async def _advance_to_star_count(message: Message, state: FSMContext, paths: list[str], media_type: str) -> None:
    await state.update_data(
        media_relative_path=encode_media_paths(paths),
        media_type=media_type,
        album_paths=[],
        album_group_id=None,
    )
    await state.set_state(OperatorPaidStates.waiting_star_count)
    n = len(paths)
    suffix = f" (альбом: {n} фото)" if n > 1 else ""
    await message.answer(
        f"Шаг 2/3: укажите цену в ⭐ (число от 1 до 25000).{suffix}",
        parse_mode="HTML",
    )


async def _schedule_album_finalize(
    message: Message,
    state: FSMContext,
    *,
    media_group_id: str,
) -> None:
    chat_id = int(message.chat.id)
    key = (chat_id, media_group_id)
    prev = _album_finalize_tasks.pop(key, None)
    if prev is not None:
        prev.cancel()

    async def _job() -> None:
        try:
            await asyncio.sleep(_ALBUM_COLLECT_SEC)
            data = await state.get_data()
            if data.get("album_group_id") != media_group_id:
                return
            paths = list(data.get("album_paths") or [])
            if not paths:
                return
            await _advance_to_star_count(message, state, paths, "photo")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("stars business album finalize failed")

    _album_finalize_tasks[key] = asyncio.create_task(_job())


@router.message(OperatorPaidStates.waiting_media, F.photo | F.video)
async def paid_got_media(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    owner_id = int(data["owner_tg_user_id"])
    rel, media_type = await _download_message_media(message, bot, owner_id)

    mgid = (message.media_group_id or "").strip()
    if mgid and message.photo:
        paths = list(data.get("album_paths") or [])
        paths.append(rel)
        if len(paths) > _MAX_ALBUM_PHOTOS:
            paths = paths[:_MAX_ALBUM_PHOTOS]
        await state.update_data(album_paths=paths, album_group_id=mgid)
        if len(paths) == 1:
            await message.answer(
                f"Собираю альбом… (до {_MAX_ALBUM_PHOTOS} фото одной группой).",
            )
        if len(paths) >= _MAX_ALBUM_PHOTOS:
            await _advance_to_star_count(message, state, paths, "photo")
            return
        await _schedule_album_finalize(message, state, media_group_id=mgid)
        return

    if message.video and mgid:
        await message.answer("В paid media альбом только из фото. Отправьте одно видео без группы.")
        return

    await _advance_to_star_count(message, state, [rel], media_type)


@router.message(OperatorPaidStates.waiting_media)
async def paid_media_invalid(message: Message) -> None:
    await message.answer("Нужно фото или видео одним сообщением.")


@router.message(OperatorPaidStates.waiting_star_count, F.text)
async def paid_got_stars(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace("⭐", "").replace(" ", "")
    if not raw.isdigit():
        await message.answer("Введите целое число звёзд, например: 50")
        return
    stars = int(raw)
    if stars < 1 or stars > 25_000:
        await message.answer("Цена должна быть от 1 до 25000 ⭐.")
        return
    data = await state.get_data()
    owner_id = int(data["owner_tg_user_id"])
    await state.update_data(star_count=stars)
    async with SessionLocal() as session:
        chats = await list_fan_chats(session, owner_id)
    await state.set_state(OperatorPaidStates.waiting_recipient)
    if chats:
        step3 = (
            "Шаг 3/3: нажмите фана в списке ниже или <b>перешлите</b> сюда его сообщение.\n"
            "🟢/🔴 у кнопки — окно 24ч (входящее от фана OWNER)."
        )
    else:
        step3 = (
            "Шаг 3/3: <b>кнопок нет</b> — бот ещё не кэшировал диалоги OWNER с фанами.\n\n"
            "Как указать получателя:\n"
            "1) Фан пишет OWNER в личку → через минуту снова /paid или /chats;\n"
            "2) <b>Перешлите</b> сюда сообщение фана (отправитель должен быть виден);\n"
            "3) Отправьте <b>числовой Telegram id</b> фана (например из @userinfobot).\n\n"
            "/chats — список кэша."
        )
    await message.answer(
        step3,
        parse_mode="HTML",
        reply_markup=fan_pick_kb(chats),
    )


@router.callback_query(OperatorPaidStates.waiting_recipient, F.data.startswith("sb:fan:"))
async def paid_pick_fan(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        fan_id = int((callback.data or "").split(":")[-1])
        await _goto_confirm(callback, state, fan_chat_id=fan_id)
    except Exception:
        log.exception("stars business paid_pick_fan failed")
        await callback.answer("Ошибка выбора фана. Попробуйте /paid снова.", show_alert=True)


@router.message(OperatorPaidStates.waiting_recipient, F.text)
async def paid_recipient_text(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if raw.isdigit():
        await _goto_confirm_message(message, state, fan_chat_id=int(raw))
        return
    await message.answer(
        "На шаге 3: кнопка фана, <b>пересылка</b> его сообщения или числовой id.\n/cancel — отмена.",
        parse_mode="HTML",
    )


@router.message(OperatorPaidStates.waiting_recipient)
async def paid_recipient_forward(message: Message, state: FSMContext) -> None:
    fan_id = fan_chat_id_from_forward(message)
    if fan_id is None:
        if message.forward_date or message.forward_origin:
            await message.answer(
                "Не вижу id фана в пересылке (скрыта анонимная пересылка).\n"
                "Перешлите без «скрыть отправителя» или отправьте числовой Telegram id фана.",
            )
        return
    await _goto_confirm_message(message, state, fan_chat_id=fan_id)


async def _goto_confirm(callback: CallbackQuery, state: FSMContext, *, fan_chat_id: int) -> None:
    await callback.answer()
    if not callback.message:
        return
    await _finalize_recipient(callback.message, state, fan_chat_id=fan_chat_id)


async def _goto_confirm_message(message: Message, state: FSMContext, *, fan_chat_id: int) -> None:
    await _finalize_recipient(message, state, fan_chat_id=fan_chat_id)


async def _finalize_recipient(message: Message, state: FSMContext, *, fan_chat_id: int) -> None:
    data = await state.get_data()
    owner_id = int(data["owner_tg_user_id"])
    operator_id = int(data["operator_tg_user_id"])
    stars = int(data["star_count"])
    rel = str(data["media_relative_path"])
    media_type = str(data.get("media_type") or "photo")

    async with SessionLocal() as session:
        chats = await list_fan_chats(session, owner_id)
        chat_row = next((c for c in chats if int(c.fan_chat_id) == fan_chat_id), None)
        order = await create_order(
            session,
            owner_tg_user_id=owner_id,
            operator_tg_user_id=operator_id,
            fan_chat_id=fan_chat_id,
            star_count=stars,
            caption=None,
            media_relative_path=rel,
            media_type=media_type,
        )
        await session.commit()
        order_id = order.id

    await state.set_state(OperatorPaidStates.confirm_send)
    await state.update_data(order_id=order_id, fan_chat_id=fan_chat_id)
    # Без строки в кэше (ручной id) нельзя считать окно закрытым — раньше всегда показывали ложный ⚠️.
    if chat_row is None:
        window_note = (
            "\n\nℹ️ Фан не в кэше бота (id вручную или кэш ещё не успел). "
            "Если он недавно писал <b>OWNER в личку</b> — жмите «Отправить»; "
            "Telegram сам проверит 24ч. Ошибка будет только при BUSINESS_CHAT_INACTIVE."
        )
    elif chat_window_open(chat_row.last_inbound_at):
        window_note = "\n\n🟢 По кэшу: входящее от фана было менее 24ч назад."
    else:
        window_note = (
            "\n\n⚠️ По кэшу: последнее входящее от фана >24ч — "
            "возможен BUSINESS_CHAT_INACTIVE."
        )
    await message.answer(
        f"Проверка:\n"
        f"• фан chat_id: <code>{fan_chat_id}</code>\n"
        f"• цена: <b>{stars} ⭐</b>\n"
        f"• заказ #{order_id}{window_note}",
        parse_mode="HTML",
        reply_markup=confirm_send_kb(order_id),
    )


@router.callback_query(OperatorPaidStates.confirm_send, F.data.startswith("sb:send:"))
async def paid_confirm_send(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    if not order_id:
        await callback.message.answer("Сессия устарела. Начните /paid заново.") if callback.message else None
        await state.clear()
        return

    async with SessionLocal() as session:
        conn = await get_active_connection(session)
        from app.db.models import StarsBusinessOrder

        order = await session.get(StarsBusinessOrder, order_id)
        if not conn or not order:
            await callback.message.answer("OWNER не подключён или заказ не найден.") if callback.message else None
            await state.clear()
            return
        result = await send_paid_media_order(bot, conn=conn, order=order)
        if result.ok and result.message_id is not None:
            await mark_order_sent(session, order, platform_message_id=result.message_id)
            await session.commit()
            await state.clear()
            if callback.message:
                await callback.message.answer(
                    f"✅ Paid media отправлено (msg {result.message_id}). "
                    f"Заказ #{order_id}, payload для оплаты: {order_id}."
                )
            return
        await mark_order_failed(session, order, error_code=result.error_code or "SEND_FAILED")
        await session.commit()
        await state.clear()
        if callback.message:
            await callback.message.answer(result.error_text or "Ошибка отправки.")
