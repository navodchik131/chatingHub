"""Старые pending studio jobs не должны автоматически перегенерироваться."""

from app.services.studio_jobs import (
    STALE_PENDING_JOB_MESSAGE,
    STUDIO_PENDING_MAX_AGE_MINUTES,
)


def test_stale_pending_constants() -> None:
    assert STUDIO_PENDING_MAX_AGE_MINUTES == 30
    assert "устарела" in STALE_PENDING_JOB_MESSAGE.lower()
