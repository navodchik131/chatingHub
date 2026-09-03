"""Outline motion-видео в отдельном subprocess: OOM rembg не валит uvicorn."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from app.config import BACKEND_DIR, settings

log = logging.getLogger(__name__)

# На 2 GB VPS — один outline за раз (rembg + OpenCV).
_OUTLINE_SUBPROCESS_LOCK = asyncio.Lock()

_OOM_EXIT_CODES = frozenset({137, -9, 9, 247, -247})


def apply_subprocess_memory_limit_mb(limit_mb: int | None) -> None:
    """RLIMIT_AS в дочернем процессе — мягкий предел до OOM всего контейнера."""
    if limit_mb is None or limit_mb <= 0:
        return
    try:
        import resource

        cap = int(limit_mb) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
        log.info("motion outline subprocess: RLIMIT_AS=%s MB", limit_mb)
    except (ImportError, OSError, ValueError) as e:
        log.warning("motion outline subprocess: memory limit not applied: %s", e)


def render_motion_outline_from_source(owner_id: int, file_id: str, source: Path) -> None:
    """Синхронный рендер + публикация outline (вызывается из CLI subprocess)."""
    from app.services.motion_video_outline import (
        process_motion_video_outline,
        publish_outline_for_owner,
        resolve_motion_video_file,
        resolve_motion_video_source,
    )
    from app.services.studio_motion_video import (
        extract_motion_audio_file,
        mux_original_audio_onto_video,
    )

    fid = str(file_id or "").strip()[:128]
    result = process_motion_video_outline(source)
    try:
        publish_outline_for_owner(owner_id=owner_id, file_id=fid, outline=result.outline_path)
        published = resolve_motion_video_file(owner_id, fid)
        audio_src = resolve_motion_video_source(owner_id, fid) or source
        if published is not None:
            mux_original_audio_onto_video(published, audio_src)
        extract_motion_audio_file(owner_id=owner_id, file_id=fid, source=audio_src)
        if resolve_motion_video_source(owner_id, fid) is None:
            marker_path = (
                resolve_motion_video_file(owner_id, fid) or source
            ).parent / f"{fid}.outlined"
            marker_path.write_text("1", encoding="utf-8")
    finally:
        result.outline_path.unlink(missing_ok=True)


def render_motion_outline_job_sync(owner_id: int, file_id: str) -> None:
    """CLI entry: найти source и отрендерить outline на диск."""
    from app.services.motion_video_outline import resolve_motion_video_source
    from app.services.studio_motion_video import resolve_motion_video_file

    fid = str(file_id or "").strip()[:128]
    if not fid:
        raise RuntimeError("Не указан motion_video_file_id.")

    source = resolve_motion_video_source(owner_id, fid)
    if source is None:
        legacy = resolve_motion_video_file(owner_id, fid)
        if legacy is None:
            raise RuntimeError("Референс-видео не найдено. Загрузите файл снова.")
        source = legacy

    if not source.is_file():
        raise RuntimeError("Исходный файл референс-видео отсутствует на сервере.")

    render_motion_outline_from_source(owner_id, fid, source)


def _outline_subprocess_cmd(owner_id: int, file_id: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "app.workers.motion_outline_cli",
        "--owner-id",
        str(int(owner_id)),
        "--file-id",
        str(file_id).strip()[:128],
    ]


def _format_subprocess_failure(returncode: int, stderr: bytes) -> str:
    err_tail = (stderr or b"").decode("utf-8", errors="replace").strip()
    if returncode in _OOM_EXIT_CODES:
        return (
            "Нехватка памяти при обработке силуэта (rembg/OpenCV). "
            "Укоротите референс-видео или добавьте swap на сервере."
            + (f" ({err_tail[:200]})" if err_tail else "")
        )
    if err_tail:
        return err_tail[:2000]
    return f"Outline subprocess завершился с кодом {returncode}"


async def run_motion_outline_in_subprocess(owner_id: int, file_id: str) -> None:
    """Запускает outline в дочернем процессе; API остаётся живым при OOM worker."""
    if not settings.motion_outline_subprocess_enabled:
        raise RuntimeError("motion outline subprocess disabled")

    fid = str(file_id or "").strip()[:128]
    timeout_sec = max(60, int(settings.motion_outline_render_timeout_sec) + 120)

    async with _OUTLINE_SUBPROCESS_LOCK:
        log.info(
            "motion outline: spawning subprocess owner=%s file_id=%s timeout=%ss",
            owner_id,
            fid,
            timeout_sec,
        )
        proc = await asyncio.create_subprocess_exec(
            *_outline_subprocess_cmd(owner_id, fid),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(BACKEND_DIR),
            env=os.environ.copy(),
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(
                f"Превышено время обработки силуэта ({timeout_sec} с). "
                "Укоротите референс-видео и попробуйте снова."
            ) from None

        if proc.returncode != 0:
            log.error(
                "motion outline subprocess failed rc=%s stderr=%s",
                proc.returncode,
                (stderr or b"")[:800],
            )
            raise RuntimeError(_format_subprocess_failure(proc.returncode or -1, stderr or b""))

        if stdout:
            line = stdout.decode("utf-8", errors="replace").strip()
            if line:
                log.info("motion outline subprocess ok: %s", line[:240])
