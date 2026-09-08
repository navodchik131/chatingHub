"""Outfit anchor для карусели — только явная привязка к master."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def test_find_outfit_generation_for_master_only_explicit_link():
    from app.services.studio_outfit_anchor import find_outfit_generation_for_master

    master = SimpleNamespace(
        id=50,
        user_id=1,
        studio_model_id=3,
        outfit_generation_id=99,
        created_at=None,
    )
    linked = SimpleNamespace(id=99, user_id=1)

    session = MagicMock()
    session.get = AsyncMock(return_value=linked)

    gid = asyncio.run(find_outfit_generation_for_master(session, master))
    assert gid == 99
    session.execute.assert_not_called()


def test_find_outfit_generation_for_master_no_heuristic_stale_dress():
    from app.services.studio_outfit_anchor import find_outfit_generation_for_master

    master = SimpleNamespace(
        id=50,
        user_id=1,
        studio_model_id=3,
        outfit_generation_id=None,
        created_at=None,
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    session.execute = AsyncMock()

    gid = asyncio.run(find_outfit_generation_for_master(session, master))
    assert gid is None
    session.execute.assert_not_called()
