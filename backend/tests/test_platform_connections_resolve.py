"""Tests for conversation → platform connection resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio

import pytest

from app.services.platform_connections import resolve_fanvue_connection_for_conversation


def test_resolve_fanvue_falls_back_when_stale_connection_id():
    conv = SimpleNamespace(
        id=10,
        fanvue_connection_id=999,
        external_topic_id="creator-uuid",
        studio_model_id=3,
    )
    live = SimpleNamespace(id=2, creator_uuid="creator-uuid", studio_model_id=3)
    session = AsyncMock()
    calls = {"n": 0}

    async def _scalar(stmt):
        _ = stmt
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return live

    session.scalar = AsyncMock(side_effect=_scalar)

    async def _run():
        return await resolve_fanvue_connection_for_conversation(
            session, conv, owner_id=1, repair=True
        )

    row = asyncio.run(_run())
    assert row is live
    assert conv.fanvue_connection_id == 2
