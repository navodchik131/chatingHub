from __future__ import annotations

import json
import logging

from aiogram.types import Update
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.fanvue.handlers import (
    ingest_fanvue_message_received,
    is_fanvue_message_read_payload,
)
from app.connectors.fanvue.signature import verify_fanvue_webhook_signature
from app.connectors.telegram.ingest import ingest_telegram_dm, ingest_telegram_message_reaction
from app.db.models import FanvueConnection, TelegramConnection
from app.db.session import get_session
from app.services.fanvue_connection import (
    fanvue_platform_webhook_signing_secret,
    resolve_fanvue_webhook_signing_secret,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _process_fanvue_webhook(
    session: AsyncSession,
    *,
    raw: bytes,
    sig_header: str | None,
    conn: FanvueConnection,
) -> dict:
    try:
        signing = resolve_fanvue_webhook_signing_secret(conn)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    if not verify_fanvue_webhook_signature(raw, sig_header, signing):
        log.warning(
            "fanvue webhook: invalid signature creator=%s",
            (conn.creator_uuid or "")[:8],
        )
        raise HTTPException(status_code=401, detail="invalid fanvue signature")

    try:
        body = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="invalid json body") from e

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="json must be an object")

    if is_fanvue_message_read_payload(body):
        return {"ok": True, "skipped": "message.read"}

    if "message" in body and "sender" in body:
        recipient = str(body.get("recipientUuid") or "").strip()
        if recipient and recipient != conn.creator_uuid:
            raise HTTPException(status_code=400, detail="recipient mismatch")
        try:
            return await ingest_fanvue_message_received(session, body, conn.user_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception:
            log.exception("fanvue message ingest failed")
            raise HTTPException(status_code=500, detail="ingest failed") from None

    raise HTTPException(status_code=400, detail="unsupported fanvue webhook payload")


@router.post("/telegram/{secret}")
async def telegram_webhook(
    secret: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    conn = await session.scalar(
        select(TelegramConnection).where(
            TelegramConnection.webhook_secret == secret,
            TelegramConnection.is_active.is_(True),
        )
    )
    if not conn:
        raise HTTPException(status_code=404, detail="unknown webhook")

    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="invalid json") from e

    try:
        upd = Update.model_validate(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail="invalid telegram update") from e

    if upd.message_reaction:
        await ingest_telegram_message_reaction(
            conn.user_id,
            upd.message_reaction,
            source="webhook",
        )
        return {"ok": True}

    if not upd.message:
        return {"ok": True, "skipped": "no_message"}
    await ingest_telegram_dm(conn.user_id, upd.message, source="webhook")
    return {"ok": True}


@router.post("/fanvue")
async def fanvue_webhook_platform(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Единый webhook URL для приложения ChatingApp (маршрутизация по recipientUuid)."""
    if not fanvue_platform_webhook_signing_secret():
        raise HTTPException(status_code=404, detail="platform fanvue webhook disabled")

    raw = await request.body()
    sig_header = request.headers.get("x-fanvue-signature") or request.headers.get(
        "X-Fanvue-Signature"
    )
    try:
        body = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="invalid json body") from e
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="json must be an object")

    recipient = str(body.get("recipientUuid") or "").strip()
    if not recipient:
        raise HTTPException(status_code=400, detail="missing recipientUuid")

    conn = await session.scalar(
        select(FanvueConnection).where(FanvueConnection.creator_uuid == recipient)
    )
    if not conn:
        log.info("fanvue webhook: unknown creator %s", recipient[:8])
        return {"ok": True, "skipped": "unknown_creator"}

    log.info("fanvue webhook hit creator=%s", recipient[:8])
    return await _process_fanvue_webhook(
        session, raw=raw, sig_header=sig_header, conn=conn
    )


@router.post("/fanvue/{secret}")
async def fanvue_webhook_legacy(
    secret: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Legacy: per-user webhook path (до platform webhook)."""
    conn = await session.scalar(
        select(FanvueConnection).where(FanvueConnection.webhook_secret == secret)
    )
    if not conn:
        raise HTTPException(status_code=404, detail="unknown webhook")

    raw = await request.body()
    sig_header = request.headers.get("x-fanvue-signature") or request.headers.get(
        "X-Fanvue-Signature"
    )
    return await _process_fanvue_webhook(
        session, raw=raw, sig_header=sig_header, conn=conn
    )
