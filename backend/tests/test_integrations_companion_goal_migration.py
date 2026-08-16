"""Integrations self-heal when companion_goal columns are missing."""

from __future__ import annotations

from sqlalchemy.exc import DBAPIError

from app.api.integrations_routes import _missing_companion_goal_column


def test_missing_companion_goal_column_postgres_message() -> None:
    exc = DBAPIError(
        "SELECT ...",
        {},
        Exception('column "companion_goal_preset" does not exist'),
    )
    assert _missing_companion_goal_column(exc) is True


def test_missing_companion_goal_column_sqlite_message() -> None:
    exc = DBAPIError(
        "SELECT ...",
        {},
        Exception("no such column: companion_goal_preset"),
    )
    assert _missing_companion_goal_column(exc) is True


def test_missing_companion_goal_column_unrelated() -> None:
    exc = DBAPIError("SELECT ...", {}, Exception("column foo does not exist"))
    assert _missing_companion_goal_column(exc) is False
