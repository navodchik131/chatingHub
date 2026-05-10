from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.config import settings
from app.db.models import StudioGeneration
from app.db.session import SessionLocal
from app.services.studio_generation_storage import safe_delete_generation_file

log = logging.getLogger(__name__)

_BATCH = 250


async def purge_studio_generations_expired() -> int:
    """Удаляет с диска и из БД архив студии старше retention. 0 в настройке — без работы."""
    days = settings.studio_generations_retention_days
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total = 0
    async with SessionLocal() as session:
        while True:
            stmt = (
                select(StudioGeneration.id, StudioGeneration.relative_path)
                .where(StudioGeneration.created_at < cutoff)
                .limit(_BATCH)
            )
            rows = (await session.execute(stmt)).all()
            if not rows:
                break
            ids = [r[0] for r in rows]
            for _id, rel in rows:
                safe_delete_generation_file(rel)
            await session.execute(delete(StudioGeneration).where(StudioGeneration.id.in_(ids)))
            await session.commit()
            total += len(ids)
    if total:
        log.info(
            "studio generations retention: removed %s row(s) (older than %s day(s))",
            total,
            days,
        )
    return total
