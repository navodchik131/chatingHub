from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.fanvue.client import FanvueAPIError, send_direct_message
from app.connectors.fanvue.handlers import (
    ingest_fanvue_message_received,
    is_fanvue_message_read_payload,
)
from app.connectors.fanvue.signature import verify_fanvue_webhook_signature
from app.connectors.telegram.state import get_bot, get_telegram_api_status
from app.db.models import MessageDirection, Platform
from app.config import BACKEND_DIR, settings
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
from app.db.session import get_session
from app.schemas import ConversationOut, ConversationWithPreview, MessageOut, ReplyIn
from app.services.realtime import hub
from app.services.translation import translate_from_russian

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health")
async def api_health(session: AsyncSession = Depends(get_session)) -> dict:
    """Проверка API и БД: путь к файлу SQLite, число диалогов и сообщений."""
    n_conv, n_msg = await count_rows(session)
    db_path = ""
    if settings.database_url.startswith("sqlite+aiosqlite"):
        rest = settings.database_url.replace("sqlite+aiosqlite:///", "", 1)
        db_path = rest
    tg = get_telegram_api_status()
    return {
        "ok": True,
        "database_file": db_path,
        "backend_dir": str(BACKEND_DIR),
        "conversations_count": n_conv,
        "messages_count": n_msg,
        "telegram_bot_configured": bool(settings.bot_token),
        "telegram_api_reachable": tg.get("reachable"),
        "telegram_bot_username": tg.get("username"),
        "telegram_api_error": tg.get("error"),
        "telegram_proxy_configured": bool(
            (settings.telegram_proxy or "").strip()
        ),
        "fanvue_webhook_secret_configured": bool(
            (settings.fanvue_webhook_secret or "").strip()
        ),
        "fanvue_access_token_configured": bool(
            (settings.fanvue_access_token or "").strip()
        ),
    }


@router.get("/conversations", response_model=list[ConversationWithPreview])
async def api_list_conversations(
    session: AsyncSession = Depends(get_session),
) -> list[ConversationWithPreview]:
    convs = await list_conversations(session)
    out: list[ConversationWithPreview] = []
    for c in convs:
        last = await get_last_message(session, c.id)
        preview = None
        if last:
            preview = (last.text_translated or last.text_original)[:280]
        unread = await unread_inbound_count(session, c.id)
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
) -> dict:
    conv = await get_conversation(session, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    await mark_conversation_read(session, conv_id)
    await session.commit()
    return {"ok": True}


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def api_messages(
    conv_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[MessageOut]:
    conv = await get_conversation(session, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    rows = await list_messages(session, conv_id)
    return [MessageOut.model_validate(m) for m in rows]


@router.post("/conversations/{conv_id}/reply", response_model=MessageOut)
async def api_reply(
    conv_id: int,
    body: ReplyIn,
    session: AsyncSession = Depends(get_session),
) -> MessageOut:
    text_ru = body.text.strip()
    if not text_ru:
        raise HTTPException(status_code=400, detail="empty text")

    conv = await get_conversation(session, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")

    target_lang = conv.user_lang or "en"
    outgoing = await translate_from_russian(text_ru, target_lang)
    # Переводчики иногда возвращают пустую строку для «только эмодзи» — тогда шлём как есть
    if not (outgoing or "").strip():
        outgoing = text_ru

    if conv.platform == Platform.telegram:
        bot = get_bot()
        if not bot:
            raise HTTPException(
                status_code=503, detail="Telegram bot not running (check BOT_TOKEN)"
            )
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
    elif conv.platform == Platform.fanvue:
        try:
            await send_direct_message(conv.external_chat_id, outgoing)
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
    await mark_conversation_read(session, conv.id)
    await session.commit()
    await session.refresh(row)

    await hub.broadcast(
        {
            "type": "new_message",
            "conversation_id": conv.id,
            "message": MessageOut.model_validate(row).model_dump(mode="json"),
        }
    )
    return MessageOut.model_validate(row)


@router.websocket("/ws")
async def websocket_updates(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        log.debug("ws disconnected")
    finally:
        await hub.disconnect(ws)


@router.post("/connectors/fanvue/webhook")
async def fanvue_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Входящие события Fanvue (Message Received, Message Read и т.д.).
    Подпись: заголовок ``X-Fanvue-Signature``, секрет ``FANVUE_WEBHOOK_SECRET``.
    """
    raw = await request.body()
    sig_header = request.headers.get("x-fanvue-signature") or request.headers.get(
        "X-Fanvue-Signature"
    )
    secret = (settings.fanvue_webhook_secret or "").strip()
    if secret:
        if not verify_fanvue_webhook_signature(raw, sig_header, secret):
            raise HTTPException(status_code=401, detail="invalid fanvue signature")
    else:
        log.warning(
            "FANVUE_WEBHOOK_SECRET not set — webhook signatures are not verified"
        )

    try:
        body = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="invalid json body") from e

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="json must be an object")

    if is_fanvue_message_read_payload(body):
        return {"ok": True, "skipped": "message.read"}

    if "message" in body and "sender" in body:
        try:
            return await ingest_fanvue_message_received(session, body)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            log.exception("fanvue message ingest failed")
            raise HTTPException(status_code=500, detail="ingest failed") from e

    raise HTTPException(status_code=400, detail="unsupported fanvue webhook payload")
