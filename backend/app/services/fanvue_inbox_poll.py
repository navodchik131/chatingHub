"""Фоновый опрос Fanvue inbox — подстраховка пропущенных webhook."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.db.models import FanvueConnection
from app.db.session import SessionLocal
from app.services.fanvue_sync import poll_fanvue_inbox

log = logging.getLogger(__name__)


async def run_fanvue_inbox_poll_once() -> None:
    async with SessionLocal() as session:
        rows = (await session.scalars(select(FanvueConnection))).all()
        for conn in rows:
            try:
                stats = await poll_fanvue_inbox(session, conn=conn)
                imported = int(stats.get("messages_imported") or 0)
                if imported:
                    log.info(
                        "fanvue inbox poll user=%s imported=%s skipped=%s",
                        conn.user_id,
                        imported,
                        stats.get("messages_skipped"),
                    )
            except Exception:
                log.warning("fanvue inbox poll failed user=%s", conn.user_id, exc_info=True)


async def fanvue_inbox_poll_loop() -> None:
    interval = int(settings.fanvue_inbox_poll_interval_seconds)
    if interval <= 0:
        log.info("Fanvue inbox poll disabled (FANVUE_INBOX_POLL_INTERVAL_SECONDS=0)")
        return
    await asyncio.sleep(15)
    while True:
        try:
            await run_fanvue_inbox_poll_once()
        except Exception:
            log.exception("fanvue inbox poll loop error")
        await asyncio.sleep(interval)


async def background_sync_fanvue_chat(
    owner_user_id: int,
    fan_uuid: str,
    fan_display: str = "",
) -> None:
    """После исходящего — подтянуть ответ фана, если webhook не пришёл."""
    from app.services.fanvue_sync import sync_fanvue_single_chat_recent

    async with SessionLocal() as session:
        conn = await session.scalar(
            select(FanvueConnection).where(FanvueConnection.user_id == owner_user_id)
        )
        if not conn:
            return
        try:
            n = await sync_fanvue_single_chat_recent(
                session,
                conn=conn,
                fan_uuid=fan_uuid,
                fan_display=fan_display,
            )
            if n:
                log.info(
                    "fanvue post-reply sync user=%s fan=%s imported=%s",
                    owner_user_id,
                    fan_uuid[:8],
                    n,
                )
        except Exception:
            log.warning(
                "fanvue post-reply sync failed user=%s fan=%s",
                owner_user_id,
                fan_uuid[:8],
                exc_info=True,
            )
