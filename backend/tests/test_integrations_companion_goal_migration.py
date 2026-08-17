"""Integrations self-heal when companion_goal columns are missing."""

from __future__ import annotations

from sqlalchemy.exc import DBAPIError

from app.api.integrations_routes import (
    _companion_mode_fields,
    _integration_status_fallback,
    _missing_connection_companion_column,
)


def test_missing_connection_companion_column_postgres_goal() -> None:
    exc = DBAPIError(
        "SELECT ...",
        {},
        Exception('column "companion_goal_preset" does not exist'),
    )
    assert _missing_connection_companion_column(exc) is True


def test_missing_connection_companion_column_postgres_mode() -> None:
    exc = DBAPIError(
        "SELECT ...",
        {},
        Exception('column "companion_mode" of relation "telegram_user_sessions" does not exist'),
    )
    assert _missing_connection_companion_column(exc) is True


def test_missing_connection_companion_column_sqlite_message() -> None:
    exc = DBAPIError(
        "SELECT ...",
        {},
        Exception("no such column: companion_goal_preset"),
    )
    assert _missing_connection_companion_column(exc) is True


def test_missing_connection_companion_column_unrelated() -> None:
    exc = DBAPIError("SELECT ...", {}, Exception("column foo does not exist"))
    assert _missing_connection_companion_column(exc) is False


def test_integration_status_fallback_shape() -> None:
    out = _integration_status_fallback()
    assert out.telegram_configured is False
    assert out.llm_configured in (True, False)
    assert out.max_connections_per_platform == 1


def test_companion_mode_fields_skip_unloaded_row() -> None:
    class Row:
        pass

    row = Row()
    fields = _companion_mode_fields(row, include=False)
    assert fields["companion_mode"] == "off"
    assert fields["companion_delay_min_sec"] == 5
