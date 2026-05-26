"""Тесты доступа участников к моделям студии и чатам."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.db.models import Conversation, Platform, User
from app.services.workspace_model_access import (
    apply_studio_model_id_filter,
    filter_conversations_for_member,
    member_allowed_studio_model_ids,
)


class _FakeScalars:
    def __init__(self, values: list) -> None:
        self._values = values

    def all(self) -> list:
        return self._values


class _FakeResult:
    def __init__(self, values: list) -> None:
        self._values = values

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._values)


class _FakeSession:
    def __init__(self, model_ids: list[int]) -> None:
        self._model_ids = model_ids

    async def execute(self, _stmt):  # noqa: ANN001
        return _FakeResult(self._model_ids)


def _owner() -> User:
    u = User(id=1, email="o@test", hashed_password="x")
    u.parent_user_id = None
    return u


def _member(model_ids: list[int] | None = None) -> User:
    u = User(id=2, email="m@test", hashed_password="x", parent_user_id=1)
    u.permissions_mask = 7
    return u


@pytest.mark.asyncio
async def test_owner_has_no_model_filter() -> None:
    session = _FakeSession([1, 2])
    allowed = await member_allowed_studio_model_ids(session, _owner())
    assert allowed is None


@pytest.mark.asyncio
async def test_member_empty_allowlist() -> None:
    session = _FakeSession([])
    allowed = await member_allowed_studio_model_ids(session, _member())
    assert allowed == set()


@pytest.mark.asyncio
async def test_member_with_models() -> None:
    session = _FakeSession([3, 5])
    allowed = await member_allowed_studio_model_ids(session, _member())
    assert allowed == {3, 5}


def test_apply_filter_owner_unchanged() -> None:
    from sqlalchemy import select
    from app.db.models import UserStudioModel

    stmt = select(UserStudioModel)
    out = apply_studio_model_id_filter(stmt, UserStudioModel.id, None)
    assert out is stmt


@pytest.mark.asyncio
async def test_filter_conversations_for_member() -> None:
    owner = _owner()
    member = _member()
    session = _FakeSession([10])
    conv_ok = Conversation(
        id=1,
        user_id=1,
        platform=Platform.telegram,
        external_chat_id="1",
        studio_model_id=10,
    )
    conv_hidden = Conversation(
        id=2,
        user_id=1,
        platform=Platform.telegram,
        external_chat_id="2",
        studio_model_id=None,
    )
    conv_other = Conversation(
        id=3,
        user_id=1,
        platform=Platform.telegram,
        external_chat_id="3",
        studio_model_id=99,
    )
    out = await filter_conversations_for_member(
        session, member, [conv_ok, conv_hidden, conv_other]
    )
    assert [c.id for c in out] == [1]
