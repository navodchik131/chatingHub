"""Фоновые циклы API/worker — разделение по APP_ROLE."""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.services.studio_generation_storage import retry_pending_studio_archives
from app.services.studio_generations_retention import purge_studio_generations_expired
from app.services.studio_runtime_cleanup import purge_studio_runtime_artifacts

log = logging.getLogger(__name__)


async def studio_generations_retention_loop() -> None:
    await asyncio.sleep(120)
    while True:
        try:
            await purge_studio_generations_expired()
        except Exception:
            log.exception("Studio generations retention purge failed")
        await asyncio.sleep(max(3600, settings.studio_generations_retention_interval_hours * 3600))


async def studio_runtime_cleanup_loop() -> None:
    await asyncio.sleep(180)
    while True:
        try:
            await purge_studio_runtime_artifacts()
        except Exception:
            log.exception("Studio runtime cleanup failed")
        await asyncio.sleep(max(3600, settings.studio_runtime_cleanup_interval_hours * 3600))


async def studio_archive_retry_loop() -> None:
    await asyncio.sleep(90)
    interval = max(60, int(settings.studio_archive_retry_interval_seconds))
    while True:
        try:
            await retry_pending_studio_archives()
        except Exception:
            log.exception("Studio archive retry loop failed")
        await asyncio.sleep(interval)


def spawn_studio_maintenance_tasks() -> list[asyncio.Task[None]]:
    """Retention/cleanup/archive — в worker на prod, в API только при APP_ROLE=all."""
    if not settings.background_maintenance_in_process:
        log.info(
            "Studio maintenance loops disabled (APP_ROLE=%s)",
            settings.app_role_normalized,
        )
        return []
    tasks: list[asyncio.Task[None]] = []
    if settings.studio_generations_retention_days > 0:
        tasks.append(asyncio.create_task(studio_generations_retention_loop()))
        log.info(
            "Studio generations retention enabled: %s day(s), every %s h",
            settings.studio_generations_retention_days,
            settings.studio_generations_retention_interval_hours,
        )
    if settings.studio_runtime_cleanup_enabled:
        tasks.append(asyncio.create_task(studio_runtime_cleanup_loop()))
        log.info("Studio runtime cleanup enabled")
    if settings.studio_archive_retry_in_process:
        tasks.append(asyncio.create_task(studio_archive_retry_loop()))
        log.info(
            "Studio archive retry loop: every %s s",
            settings.studio_archive_retry_interval_seconds,
        )
    return tasks


def spawn_fanvue_poll_task() -> asyncio.Task[None] | None:
    if not settings.messaging_maintenance_in_process:
        return None
    if settings.fanvue_inbox_poll_interval_seconds <= 0:
        return None
    from app.services.fanvue_inbox_poll import fanvue_inbox_poll_loop

    log.info(
        "Fanvue inbox poll: every %s s",
        settings.fanvue_inbox_poll_interval_seconds,
    )
    return asyncio.create_task(fanvue_inbox_poll_loop())


def maintenance_loop_coroutines() -> list:
    """Корутины бесконечных maintenance-циклов (для asyncio.gather в worker/all)."""
    if not settings.background_maintenance_in_process:
        return []
    coros = []
    if settings.studio_generations_retention_days > 0:
        coros.append(studio_generations_retention_loop())
    if settings.studio_runtime_cleanup_enabled:
        coros.append(studio_runtime_cleanup_loop())
    if settings.studio_archive_retry_in_process:
        coros.append(studio_archive_retry_loop())
    return coros


def spawn_companion_maintenance_tasks() -> list[asyncio.Task[None]]:
    """Feedback/style index — на prod в messaging-worker."""
    if not settings.messaging_maintenance_in_process:
        return []
    from app.services.companion_bot.feedback import companion_feedback_loop
    from app.services.companion_bot.style_index import companion_style_index_loop

    log.info(
        "Companion feedback loop: every %s h",
        settings.companion_feedback_interval_hours,
    )
    log.info(
        "Companion style index loop: every %s h",
        settings.companion_style_index_interval_hours,
    )
    return [
        asyncio.create_task(companion_feedback_loop()),
        asyncio.create_task(companion_style_index_loop()),
    ]


def worker_process_coroutines() -> list:
    """Корутины APP_ROLE=worker — только studio jobs + studio maintenance."""
    from app.services.studio_jobs import studio_jobs_worker_loop

    coros: list = []
    if settings.studio_jobs_worker_loop_enabled:
        coros.append(studio_jobs_worker_loop())
    coros.extend(maintenance_loop_coroutines())
    return coros


def messaging_process_coroutines() -> list:
    """Корутины APP_ROLE=messaging — companion queue, Fanvue poll, companion index."""
    coros: list = []
    if settings.runs_telegram_user_worker and settings.telegram_user_worker_enabled:
        from app.connectors.telegram_user.worker import telegram_user_worker_loop

        coros.append(telegram_user_worker_loop())
    if settings.companion_jobs_worker_loop_enabled:
        from app.services.companion_bot.job_queue import companion_job_worker_loop

        coros.append(companion_job_worker_loop())
    if settings.messaging_maintenance_in_process:
        from app.services.companion_bot.feedback import companion_feedback_loop
        from app.services.companion_bot.style_index import companion_style_index_loop
        from app.services.fanvue_inbox_poll import fanvue_inbox_poll_loop

        if settings.fanvue_inbox_poll_interval_seconds > 0:
            coros.append(fanvue_inbox_poll_loop())
        coros.append(companion_feedback_loop())
        coros.append(companion_style_index_loop())
    return coros
