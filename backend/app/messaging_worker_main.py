"""Messaging worker (APP_ROLE=messaging): companion queue, Fanvue poll, companion index."""

from __future__ import annotations

import asyncio
import logging
import signal

from app.background_loops import messaging_process_coroutines
from app.config import settings
from app.db.session import init_db
from app.services.startup_security import assert_startup_security

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def _run_messaging_worker() -> None:
    if settings.app_role_normalized != "messaging":
        raise RuntimeError(
            f"messaging_worker_main требует APP_ROLE=messaging, сейчас: {settings.app_role_normalized!r}"
        )
    assert_startup_security()
    await init_db()
    if settings.companion_jobs_worker_loop_enabled:
        from app.services.companion_bot.job_queue import recover_stale_companion_jobs_on_startup

        try:
            recovered = await recover_stale_companion_jobs_on_startup(stale_minutes=10)
            if recovered:
                log.info("Companion stale jobs recovered on messaging worker startup: %s", recovered)
        except Exception:
            log.exception("Companion job recovery on messaging worker startup failed")
    coros = messaging_process_coroutines()
    if not coros:
        raise RuntimeError("messaging worker: no background loops configured")
    log.info("Messaging worker started (loops=%s)", len(coros))
    await asyncio.gather(*coros)


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(_run_messaging_worker())

    def _stop(*_args: object) -> None:
        task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _stop())

    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        log.info("Messaging worker shutdown requested")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
