"""Точка входа фонового worker-процесса (APP_ROLE=worker).

Запуск: python -m app.worker_main
Docker: CMD ["python", "-m", "app.worker_main"]
"""

from __future__ import annotations

import asyncio
import logging
import signal

from app.config import settings
from app.db.session import init_db
from app.services.startup_security import assert_startup_security
from app.services.studio_generation_storage import retry_pending_studio_archives
from app.services.studio_jobs import recover_studio_jobs_on_startup, studio_jobs_worker_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def _studio_archive_retry_loop() -> None:
    await asyncio.sleep(90)
    interval = max(60, int(settings.studio_archive_retry_interval_seconds))
    while True:
        try:
            await retry_pending_studio_archives()
        except Exception:
            log.exception("Studio archive retry loop failed")
        await asyncio.sleep(interval)


async def _run_worker() -> None:
    if settings.app_role_normalized != "worker":
        raise RuntimeError(
            f"worker_main требует APP_ROLE=worker, сейчас: {settings.app_role_normalized!r}"
        )
    assert_startup_security()
    await init_db()
    try:
        from app.services.motion_video_outline import assert_ffmpeg_tools_available

        assert_ffmpeg_tools_available()
        log.info("ffmpeg/ffprobe OK for studio worker")
    except Exception as e:
        log.error("ffmpeg/ffprobe unavailable: %s", e)
        raise
    try:
        from app.services.fx_rate import get_usd_rate

        await get_usd_rate()
    except Exception:
        log.warning("Initial CBR USD/RUB fetch failed", exc_info=True)
    try:
        await recover_studio_jobs_on_startup()
    except Exception:
        log.exception("studio jobs startup recovery failed")
    worker_coros = [
        studio_jobs_worker_loop(),
        _studio_archive_retry_loop(),
    ]
    if settings.companion_jobs_worker_loop_enabled:
        from app.services.companion_bot.job_queue import (
            companion_job_worker_loop,
            recover_stale_companion_jobs_on_startup,
        )

        try:
            recovered = await recover_stale_companion_jobs_on_startup()
            if recovered:
                log.info("Companion jobs recovered on worker startup: %s", recovered)
        except Exception:
            log.exception("Companion job recovery on worker startup failed")
        worker_coros.append(companion_job_worker_loop())
        log.info("Companion job worker loop enabled in studio-worker")
    log.info("Studio worker started (database=%s)", settings.database_url)
    await asyncio.gather(*worker_coros)


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(_run_worker())

    def _stop(*_args: object) -> None:
        task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            # Windows
            signal.signal(sig, lambda *_: _stop())

    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        log.info("Studio worker shutdown requested")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
