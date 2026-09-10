"""Проверки безопасности при старте API — fail-fast до init_db и приёма трафика."""

from __future__ import annotations

from app.config import settings

_DEV_JWT_SECRET = "dev-change-me"


def _production_like() -> bool:
    """Postgres и прочие не-sqlite URL считаем prod-like (не локальная dev-БД)."""
    return not (settings.database_url or "").startswith("sqlite")


def assert_startup_security() -> None:
    """Блокирует старт при опасных дефолтах в prod-like окружении."""
    errors: list[str] = []

    if _production_like() and (settings.jwt_secret or "").strip() == _DEV_JWT_SECRET:
        errors.append(
            "JWT_SECRET не задан или равен dev-change-me — задайте уникальный секрет в .env"
        )

    if settings.yookassa_configured and not (settings.yookassa_webhook_secret or "").strip():
        errors.append(
            "YOOKASSA_WEBHOOK_SECRET обязателен при настроенной ЮKassa "
            "(YOOKASSA_SHOP_ID + YOOKASSA_SECRET_KEY)"
        )

    if _production_like() and not (settings.jwt_media_secret or "").strip():
        errors.append(
            "JWT_MEDIA_SECRET не задан — задайте отдельный секрет для публичных медиа-URL "
            "(отличный от JWT_SECRET)"
        )

    if errors:
        raise RuntimeError(
            "Критичные проблемы конфигурации безопасности:\n- " + "\n- ".join(errors)
        )
