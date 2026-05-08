from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timezone
from io import BytesIO

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.jwt_utils import decode_token
from app.config import BACKEND_DIR, settings
from app.connectors.fanvue.client import FanvueAPIError, send_direct_message
from app.connectors.telegram.bot_for_user import open_telegram_bot_for_owner
from app.connectors.telegram.state import get_telegram_api_status
from app.db.models import FanvueConnection, MessageDirection, Platform, TelegramConnection, User
from app.db.repo import (
    add_message,
    count_rows,
    get_conversation,
    get_last_message,
    list_conversations,
    list_messages,
    mark_conversation_read,
    unread_inbound_count,
)
from app.db.session import SessionLocal, get_session
from app.schemas import (
    ConversationOut,
    ConversationPatchIn,
    ConversationWithPreview,
    MessageOut,
    ReplyIn,
)
from app.services.crypto_secret import decrypt_secret
from app.services.realtime import hub
from app.services.translation import translate_from_russian
from app.services.wavespeed_client import studio_wan_edit_tier_switch_available
from app.services.workspace import PERM_CHAT, assert_permission, workspace_owner_id

log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.get("/health")
async def api_health(session: AsyncSession = Depends(get_session)) -> dict:
    try:
        from sqlalchemy import text

        await session.execute(text("SELECT 1"))
    except Exception:
        return {"ok": False, "mode": "saas", "database": "down"}

    db_path = ""
    if settings.database_url.startswith("sqlite+aiosqlite"):
        rest = settings.database_url.replace("sqlite+aiosqlite:///", "", 1)
        db_path = rest
    n_conv, n_msg = await count_rows(session)
    tg = get_telegram_api_status()
    return {
        "ok": True,
        "mode": "saas",
        "database_file": db_path,
        "backend_dir": str(BACKEND_DIR),
        "conversations_count": n_conv,
        "messages_count": n_msg,
        "legacy_telegram_polling": bool(
            (settings.legacy_bot_token or "").strip() and settings.legacy_user_id > 0
        ),
        "telegram_api_reachable": tg.get("reachable"),
        "telegram_bot_username": tg.get("username"),
        "telegram_api_error": tg.get("error"),
        "telegram_proxy_configured": bool((settings.telegram_proxy or "").strip()),
        "yookassa_configured": settings.yookassa_configured,
        "billing_require_active_subscription": settings.billing_require_active_subscription,
        "billing_price_managed_month_rub": settings.billing_price_managed_month_rub,
        "billing_price_byok_month_rub": settings.billing_price_byok_month_rub,
        "billing_credit_pack_price_rub": settings.billing_credit_pack_price_rub,
        "billing_credit_pack_credits": settings.billing_credit_pack_credits,
        "billing_credits_min_purchase": settings.billing_credits_min_purchase,
        "billing_credits_bulk_from": settings.billing_credits_bulk_from,
        "billing_credits_unit_price_rub": float(settings.billing_credits_unit_price_rub),
        "billing_credits_bulk_unit_price_rub": float(settings.billing_credits_bulk_unit_price_rub),
        "openai_studio_configured": bool((settings.openai_api_key or "").strip()),
        "wavespeed_platform_configured": bool((settings.wavespeed_platform_api_key or "").strip()),
        "studio_prompt_credit_cost": settings.credit_cost_studio_prompt_refine,
        "studio_upscale_credit_cost": settings.credit_cost_studio_upscale,
        "studio_wan_edit_tier_switch": studio_wan_edit_tier_switch_available(),
        "studio_allow_prompt_only": settings.studio_allow_prompt_only,
        "studio_carousel_credit_cost": settings.credit_cost_studio_carousel_shot,
        "web_push_configured": settings.web_push_configured,
    }

@router.get("/conversations", response_model=list[ConversationWithPreview])
async def api_list_conversations(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ConversationWithPreview]:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    convs = await list_conversations(session, oid)
    out: list[ConversationWithPreview] = []
    for c in convs:
        last = await get_last_message(session, c.id, oid)
        preview = None
        if last:
            preview = (last.text_translated or last.text_original)[:280]
        unread = await unread_inbound_count(session, c.id, oid)
        base = ConversationOut.model_validate(c)
        out.append(
            ConversationWithPreview.model_validate(
                {
                    **base.model_dump(),
                    "last_message_preview": preview,
                    "unread_count": unread,
                }
            )
        )
    return out


@router.post("/conversations/{conv_id}/read")
async def api_mark_read(
    conv_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    conv = await get_conversation(session, conv_id, oid)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    await mark_conversation_read(session, conv_id, oid)
    await session.commit()
    return {"ok": True}


@router.get("/conversations/{conv_id}/avatar")
async def api_conversation_avatar(
    conv_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    """Фото профиля собеседника (Telegram), прокси через бэкенд — токен бота не светится во фронте."""
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    conv = await get_conversation(session, conv_id, oid)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    if conv.platform != Platform.telegram or not (conv.telegram_photo_file_id or "").strip():
        raise HTTPException(status_code=404, detail="no avatar")

    bot, close_bot = await open_telegram_bot_for_owner(session, oid)
    if not bot:
        raise HTTPException(
            status_code=503,
            detail="Нет доступа к Telegram Bot API: подключите бота или legacy polling.",
        )
    try:
        tg_file = await bot.get_file(conv.telegram_photo_file_id)
        if not tg_file.file_path:
            raise HTTPException(status_code=404, detail="no avatar")
        buf = BytesIO()
        await bot.download_file(tg_file.file_path, buf)
        data = buf.getvalue()
    finally:
        if close_bot:
            await bot.session.close()

    media_type = mimetypes.guess_type(tg_file.file_path)[0] or "application/octet-stream"
    return Response(content=data, media_type=media_type)


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def api_messages(
    conv_id: int,
    limit: int = Query(40, ge=1, le=200),
    before: int | None = Query(
        None,
        description="Подгрузка истории: сообщения с id строго меньше этого значения",
    ),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[MessageOut]:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    conv = await get_conversation(session, conv_id, oid)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    rows = await list_messages(
        session, conv_id, oid, limit=limit, before_id=before
    )
    return [MessageOut.model_validate(m) for m in rows]


@router.patch("/conversations/{conv_id}", response_model=ConversationOut)
async def api_patch_conversation(
    conv_id: int,
    body: ConversationPatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ConversationOut:
    """Обновление настроек диалога (язык исходящих и т.д.)."""
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    conv = await get_conversation(session, conv_id, oid)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")

    if "outbound_lang" in body.model_fields_set:
        conv.outbound_lang = body.outbound_lang
    await session.commit()
    await session.refresh(conv)
    return ConversationOut.model_validate(conv)


@router.post("/conversations/{conv_id}/reply", response_model=MessageOut)
async def api_reply(
    conv_id: int,
    body: ReplyIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MessageOut:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    text_ru = body.text.strip()
    if not text_ru:
        raise HTTPException(status_code=400, detail="empty text")

    conv = await get_conversation(session, conv_id, oid)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")

    forced = (conv.outbound_lang or "").strip().lower()
    target_lang = forced if forced else (conv.user_lang or "en").strip().lower() or "en"
    outgoing = await translate_from_russian(text_ru, target_lang)
    if not (outgoing or "").strip():
        outgoing = text_ru

    if conv.platform == Platform.telegram:
        row_tg = await session.scalar(
            select(TelegramConnection).where(TelegramConnection.user_id == oid)
        )
        if not row_tg:
            raise HTTPException(
                status_code=503,
                detail="Подключите Telegram-бота в настройках интеграций",
            )
        token = decrypt_secret(row_tg.bot_token_encrypted)
        proxy = (settings.telegram_proxy or "").strip()
        session_aio = AiohttpSession(proxy=proxy) if proxy else None
        bot = Bot(token=token, session=session_aio) if session_aio else Bot(token=token)
        try:
            try:
                tid = int(conv.external_topic_id)
                cid = int(conv.external_chat_id)
            except ValueError as e:
                raise HTTPException(status_code=500, detail="bad telegram ids") from e
            await bot.send_message(
                chat_id=cid,
                text=outgoing,
                direct_messages_topic_id=tid,
            )
        finally:
            await bot.session.close()
    elif conv.platform == Platform.fanvue:
        row_fv = await session.scalar(
            select(FanvueConnection).where(FanvueConnection.user_id == oid)
        )
        if not row_fv:
            raise HTTPException(
                status_code=503,
                detail="Подключите Fanvue в настройках интеграций",
            )
        fv_tok = decrypt_secret(row_fv.access_token_encrypted)
        try:
            await send_direct_message(fv_tok, conv.external_chat_id, outgoing)
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
    else:
        raise HTTPException(status_code=400, detail="unknown platform")

    conv.updated_at = datetime.now(timezone.utc)
    row = await add_message(
        session,
        conv.id,
        MessageDirection.outbound,
        text_ru,
        outgoing,
        meta=None,
    )
    await mark_conversation_read(session, conv.id, oid)
    await session.commit()
    await session.refresh(row)

    await hub.broadcast_user(
        oid,
        {
            "type": "new_message",
            "conversation_id": conv.id,
            "message": MessageOut.model_validate(row).model_dump(mode="json"),
        },
    )
    return MessageOut.model_validate(row)


@router.websocket("/ws")
async def websocket_updates(
    ws: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    if not token:
        await ws.close(code=4401)
        return
    try:
        uid = int(decode_token(token))
    except ValueError:
        await ws.close(code=4401)
        return
    async with SessionLocal() as s:
        u = await s.get(User, uid)
        if not u or not u.is_active:
            await ws.close(code=4401)
            return
        wid = workspace_owner_id(u)
    await hub.connect(ws, wid)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        log.debug("ws disconnected")
    finally:
        await hub.disconnect(ws, wid)
