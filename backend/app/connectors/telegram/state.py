"""Глобальные ссылки на Bot/Dispatcher (инициализация в main)."""

from __future__ import annotations

from typing import Any

from aiogram import Bot, Dispatcher

_bot: Bot | None = None
_dp: Dispatcher | None = None

# Последняя проверка get_me (для /api/health)
_telegram_api: dict[str, Any] = {
    "reachable": None,
    "username": None,
    "error": None,
}


def set_bot_dp(bot: Bot | None, dp: Dispatcher | None) -> None:
    global _bot, _dp
    _bot = bot
    _dp = dp


def get_bot() -> Bot | None:
    return _bot


def get_dp() -> Dispatcher | None:
    return _dp


def set_telegram_api_ok(username: str | None) -> None:
    _telegram_api["reachable"] = True
    _telegram_api["username"] = username
    _telegram_api["error"] = None


def set_telegram_api_error(msg: str) -> None:
    _telegram_api["reachable"] = False
    _telegram_api["username"] = None
    _telegram_api["error"] = msg


def set_telegram_api_not_configured() -> None:
    _telegram_api["reachable"] = None
    _telegram_api["username"] = None
    _telegram_api["error"] = None


def get_telegram_api_status() -> dict[str, Any]:
    return dict(_telegram_api)
