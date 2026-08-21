"""Фоновая чистка runtime-мусора в backend/data (не архив студии и не фото моделей)."""

from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select

from app.config import BACKEND_DIR, settings
from app.db.models import StudioJob, StudioJobStatus
from app.db.session import SessionLocal

log = logging.getLogger(__name__)

_DATA_ROOT = (BACKEND_DIR / "data").resolve()
_JOBS_ROOT = _DATA_ROOT / "studio_jobs"
_OUTLINE_CACHE_ROOT = _DATA_ROOT / "motion_outline_cache"
_POSE_REF_ROOT = _DATA_ROOT / "studio_pose_refs"
_MOTION_VIDEO_ROOT = _DATA_ROOT / "studio_motion_videos"
_WORKFLOW_REFS_ROOT = _DATA_ROOT / "workflow_refs"

_JOB_BATCH = 200


def _under_data(path: Path) -> bool:
    try:
        path.resolve().relative_to(_DATA_ROOT)
        return True
    except ValueError:
        return False


def _mtime_cutoff(days: int) -> float:
    return time.time() - max(0, days) * 86400.0


def purge_tree_files_older_than(root: Path, *, days: int) -> int:
    """Удаляет файлы старше days по mtime; затем пустые каталоги. Не трогает корневой root."""
    if days <= 0 or not root.is_dir():
        return 0
    root = root.resolve()
    if not _under_data(root):
        return 0
    cutoff = _mtime_cutoff(days)
    removed = 0
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path == root or not _under_data(path):
            continue
        try:
            if path.is_file():
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    removed += 1
            elif path.is_dir():
                try:
                    next(path.iterdir())
                except StopIteration:
                    path.rmdir()
        except OSError:
            log.warning("runtime cleanup: failed on %s", path, exc_info=True)
    return removed


async def purge_finished_studio_jobs(*, days: int) -> int:
    """Удаляет completed/failed StudioJob старше days вместе с data/studio_jobs/{id}/."""
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total = 0
    async with SessionLocal() as session:
        while True:
            stmt = (
                select(StudioJob.id)
                .where(
                    StudioJob.status.in_(
                        (StudioJobStatus.completed.value, StudioJobStatus.failed.value)
                    ),
                    StudioJob.updated_at < cutoff,
                )
                .limit(_JOB_BATCH)
            )
            ids = list((await session.scalars(stmt)).all())
            if not ids:
                break
            for job_id in ids:
                job_dir = (_JOBS_ROOT / str(job_id)).resolve()
                if _under_data(job_dir) and job_dir.is_dir():
                    shutil.rmtree(job_dir, ignore_errors=True)
            await session.execute(delete(StudioJob).where(StudioJob.id.in_(ids)))
            await session.commit()
            total += len(ids)
    return total


async def collect_studio_job_ids() -> set[int]:
    async with SessionLocal() as session:
        ids = list((await session.scalars(select(StudioJob.id))).all())
    return {int(i) for i in ids}


def purge_orphan_studio_job_dirs(*, days: int, known_ids: set[int]) -> int:
    """Удаляет каталоги studio_jobs/{id} без строки в БД, если mtime старше days."""
    if days <= 0 or not _JOBS_ROOT.is_dir():
        return 0
    cutoff = _mtime_cutoff(days)
    removed = 0
    for child in list(_JOBS_ROOT.iterdir()):
        if not child.is_dir() or not child.name.isdigit():
            continue
        job_id = int(child.name)
        if job_id in known_ids:
            continue
        try:
            if child.stat().st_mtime >= cutoff:
                continue
            if not _under_data(child):
                continue
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
        except OSError:
            log.warning("runtime cleanup: orphan job dir %s", child, exc_info=True)
    return removed


async def purge_studio_runtime_artifacts() -> dict[str, int]:
    """
    Чистит кэш/временные артефакты. Не трогает:
    studio_generations, studio_user_models, chat_media, creator_donation_covers, prompts.
    """
    stats = {
        "outline_cache_files": 0,
        "pose_ref_files": 0,
        "motion_video_files": 0,
        "workflow_ref_files": 0,
        "studio_jobs_rows": 0,
        "orphan_job_dirs": 0,
    }
    stats["outline_cache_files"] = purge_tree_files_older_than(
        _OUTLINE_CACHE_ROOT, days=int(settings.studio_outline_cache_retention_days)
    )
    stats["pose_ref_files"] = purge_tree_files_older_than(
        _POSE_REF_ROOT, days=int(settings.studio_pose_refs_retention_days)
    )
    stats["motion_video_files"] = purge_tree_files_older_than(
        _MOTION_VIDEO_ROOT, days=int(settings.studio_motion_videos_retention_days)
    )
    stats["workflow_ref_files"] = purge_tree_files_older_than(
        _WORKFLOW_REFS_ROOT, days=int(settings.studio_workflow_refs_retention_days)
    )
    stats["studio_jobs_rows"] = await purge_finished_studio_jobs(
        days=int(settings.studio_jobs_retention_days)
    )
    try:
        known = await collect_studio_job_ids()
        stats["orphan_job_dirs"] = purge_orphan_studio_job_dirs(
            days=int(settings.studio_jobs_retention_days),
            known_ids=known,
        )
    except Exception:
        log.exception("runtime cleanup: orphan job dirs failed")

    if any(stats.values()):
        log.info("studio runtime cleanup: %s", stats)
    return stats
