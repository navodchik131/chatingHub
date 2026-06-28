"""Фоновый запуск companion bot после входящего сообщения."""

from __future__ import annotations

import asyncio
import logging

from app.services.companion_bot.orchestrator import run_companion_pipeline

log = logging.getLogger(__name__)


def schedule_companion_reply(
    *,
    owner_user_id: int,
    conv_id: int,
    trigger_message_id: int,
) -> None:
    async def _run() -> None:
        try:
            await run_companion_pipeline(
                owner_user_id=owner_user_id,
                conv_id=conv_id,
                trigger_message_id=trigger_message_id,
            )
        except Exception:
            log.exception(
                "companion pipeline failed conv=%s msg=%s",
                conv_id,
                trigger_message_id,
            )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())
