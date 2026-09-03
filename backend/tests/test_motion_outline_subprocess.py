"""Тесты subprocess-outline (без rembg)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.motion_outline_subprocess import (
    _format_subprocess_failure,
    _outline_subprocess_cmd,
    run_motion_outline_in_subprocess,
)


def test_outline_subprocess_cmd():
    cmd = _outline_subprocess_cmd(42, "abc123")
    assert cmd[-4:] == ["--owner-id", "42", "--file-id", "abc123"]
    assert "app.workers.motion_outline_cli" in cmd


def test_format_subprocess_failure_oom():
    msg = _format_subprocess_failure(137, b"Killed")
    assert "памят" in msg.lower() or "Нехватка" in msg


def test_format_subprocess_failure_stderr():
    msg = _format_subprocess_failure(1, b"bad video")
    assert "bad video" in msg


def test_run_motion_outline_in_subprocess_success():
    proc = MagicMock()
    proc.returncode = 0
    proc.communicate = AsyncMock(return_value=(b"ok\n", b""))

    with patch("app.services.motion_outline_subprocess.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        asyncio.run(run_motion_outline_in_subprocess(1, "fid1"))


def test_run_motion_outline_in_subprocess_oom():
    proc = MagicMock()
    proc.returncode = 137
    proc.communicate = AsyncMock(return_value=(b"", b""))

    with patch("app.services.motion_outline_subprocess.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        with pytest.raises(RuntimeError, match="памят|Нехватка"):
            asyncio.run(run_motion_outline_in_subprocess(1, "fid1"))


def test_run_motion_outline_in_subprocess_timeout():
    proc = MagicMock()
    proc.kill = MagicMock()
    proc.wait = AsyncMock(return_value=0)

    with patch("app.services.motion_outline_subprocess.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        with patch(
            "app.services.motion_outline_subprocess.asyncio.wait_for",
            AsyncMock(side_effect=asyncio.TimeoutError),
        ):
            with pytest.raises(RuntimeError, match="Превышено время"):
                asyncio.run(run_motion_outline_in_subprocess(1, "fid1"))
    proc.kill.assert_called_once()
