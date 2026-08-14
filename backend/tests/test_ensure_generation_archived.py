import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.studio_generation_status import StudioGenerationStatus
from app.services.studio_generation_storage import (
    ensure_studio_generation_image_archived_for_external_fetch,
)


def _row(**kwargs):
    defaults = {
        "id": 99,
        "status": StudioGenerationStatus.PROVIDER_READY,
        "relative_path": "",
        "source_url": "https://cdn.example/frame.png",
        "wavespeed_task_id": "",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_ensure_skips_when_local_archive_exists():
    row = _row(relative_path="data/gen/99.png", status=StudioGenerationStatus.PROVIDER_READY)
    session = AsyncMock()

    async def _run() -> None:
        with patch(
            "app.services.studio_generation_storage.generation_has_archive_file",
            return_value=True,
        ):
            await ensure_studio_generation_image_archived_for_external_fetch(
                session, row, label="Первый кадр"
            )

    asyncio.run(_run())
    assert row.status == StudioGenerationStatus.READY
    session.add.assert_called_once_with(row)
    session.flush.assert_awaited()


def test_ensure_downloads_from_source_url():
    row = _row()
    session = AsyncMock()

    async def _run() -> None:
        with patch(
            "app.services.studio_generation_storage.generation_has_archive_file",
            side_effect=[False, True],
        ), patch(
            "app.services.studio_generation_storage.archive_studio_generation_from_url",
            new=AsyncMock(return_value=True),
        ) as archive:
            await ensure_studio_generation_image_archived_for_external_fetch(
                session, row, label="Первый кадр"
            )
        archive.assert_awaited_once()

    asyncio.run(_run())
    session.flush.assert_awaited()


def test_ensure_raises_when_nothing_works():
    row = _row()
    session = AsyncMock()

    async def _run() -> None:
        with patch(
            "app.services.studio_generation_storage.generation_has_archive_file",
            return_value=False,
        ), patch(
            "app.services.studio_generation_storage.archive_studio_generation_from_url",
            new=AsyncMock(return_value=False),
        ):
            with pytest.raises(RuntimeError, match="Первый кадр"):
                await ensure_studio_generation_image_archived_for_external_fetch(
                    session, row, label="Первый кадр"
                )

    asyncio.run(_run())
