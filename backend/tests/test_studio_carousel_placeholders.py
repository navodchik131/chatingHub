"""Server-side placeholder для карусели — видны в архиве после перезагрузки."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def test_reserve_carousel_shot_placeholders_count_and_fields():
    from unittest.mock import patch

    from app.services.studio_generation_placeholders import reserve_carousel_shot_placeholders

    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    async def _run():
        with patch(
            "app.services.funnel_analytics.record_funnel_event_for_owner_once",
            new=AsyncMock(),
        ):
            return await reserve_carousel_shot_placeholders(
                session,
                owner_id=1,
                studio_job_id=99,
                count=4,
                studio_model_id=7,
                output_aspect="9:16",
                carousel_parent_generation_id=55,
            )

    rows = asyncio.run(_run())
    assert len(rows) == 4
    assert rows[0].carousel_shot_index == 0
    assert rows[3].carousel_shot_index == 3
    assert rows[0].studio_job_id == 99
    assert rows[0].carousel_parent_generation_id == 55
    assert "Карусель 1/4" in (rows[0].prompt_excerpt or "")


def test_carousel_placeholder_ids_from_params():
    from app.services.studio_generation_placeholders import carousel_placeholder_ids_from_params

    assert carousel_placeholder_ids_from_params({"carousel_placeholder_ids": [10, 11, 12]}) == [
        10,
        11,
        12,
    ]
    assert carousel_placeholder_ids_from_params({}) == []


def test_mark_carousel_placeholders_failed_from():
    from app.services.studio_generation_placeholders import mark_carousel_placeholders_failed_from
    from app.services import studio_generation_placeholders as mod

    rows = {
        10: SimpleNamespace(id=10, status="processing"),
        11: SimpleNamespace(id=11, status="processing"),
        12: SimpleNamespace(id=12, status="processing"),
    }
    session = MagicMock()
    session.get = AsyncMock(side_effect=lambda _m, gid: rows.get(int(gid)))

    async def _fail(_session, gen, message, step):
        gen.status = "failed"
        gen.error_message = message

    orig = mod.mark_studio_generation_failed
    mod.mark_studio_generation_failed = AsyncMock(side_effect=_fail)
    try:

        async def _run():
            return await mark_carousel_placeholders_failed_from(
                session, [10, 11, 12], start_index=1, message="WaveSpeed error"
            )

        n = asyncio.run(_run())
        assert n == 2
        assert mod.mark_studio_generation_failed.await_count == 2
    finally:
        mod.mark_studio_generation_failed = orig
