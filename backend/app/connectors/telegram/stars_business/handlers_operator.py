"""OPERATOR: wizard paid media в личке с ботом."""

from __future__ import annotations

import logging
import uuid

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.connectors.telegram.stars_business.fan_window import chat_window_open
from app.connectors.telegram.stars_business.forward import fan_chat_id_from_forward
from app.connectors.telegram.stars_business.keyboards import (
    confirm_send_kb,
    fan_pick_kb,
    format_fan_list,
    operator_main_kb,
)
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
            "Команды: /paid — мастер, /chats — список диалогов, /cancel — сброс.",
            parse_mode="HTML",
            reply_markup=operator_main_kb(),
        )
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


@router.message(Command("cancel"))
@router.callback_query(F.data == "sb:cancel")
async def cmd_cancel(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text = "Отменено."
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(text)
    else:
        await event.answer(text)


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
        "Шаг 1/3: отправьте <b>фото или видео</b> (одним сообщением).\n"
        "/cancel — отмена."
    )
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(prompt, parse_mode="HTML")
    else:
        await event.answer(prompt, parse_mode="HTML")


@router.message(OperatorPaidStates.waiting_media, F.photo | F.video)
async def paid_got_media(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    owner_id = int(data["owner_tg_user_id"])
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
    rel = relative_media_path(owner_id, fname)
    await state.update_data(media_relative_path=rel, media_type=media_type)
    await state.set_state(OperatorPaidStates.waiting_star_count)
    await message.answer(
        "Шаг 2/3: укажите цену в ⭐ (число от 1 до 25000).",
        parse_mode="HTML",
    )


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
    fan_id = int((callback.data or "").split(":")[-1])
    await _goto_confirm(callback, state, fan_chat_id=fan_id)


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
        open_ = chat_window_open(chat_row.last_inbound_at) if chat_row else False
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
    warn = ""
    if not open_:
        warn = (
            "\n\n⚠️ <b>Окно закрыто</b> — входящих от фана >24ч. "
            "Telegram вернёт BUSINESS_CHAT_INACTIVE."
        )
    await message.answer(
        f"Проверка:\n"
        f"• фан chat_id: <code>{fan_chat_id}</code>\n"
        f"• цена: <b>{stars} ⭐</b>\n"
        f"• заказ #{order_id}{warn}",
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
