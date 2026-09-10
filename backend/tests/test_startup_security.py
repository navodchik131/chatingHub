import pytest

from app.config import Settings
from app.services import startup_security


def test_startup_security_allows_sqlite_dev_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        startup_security,
        "settings",
        Settings(database_url="sqlite+aiosqlite:///./data/test.db", jwt_secret="dev-change-me"),
    )
    startup_security.assert_startup_security()


def test_startup_security_blocks_default_jwt_on_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        startup_security,
        "settings",
        Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            jwt_secret="dev-change-me",
            jwt_media_secret="media-secret",
        ),
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        startup_security.assert_startup_security()


def test_startup_security_requires_media_secret_on_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        startup_security,
        "settings",
        Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            jwt_secret="prod-secret",
            jwt_media_secret="",
        ),
    )
    with pytest.raises(RuntimeError, match="JWT_MEDIA_SECRET"):
        startup_security.assert_startup_security()


def test_startup_security_requires_yookassa_webhook_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        startup_security,
        "settings",
        Settings(
            database_url="sqlite+aiosqlite:///./data/test.db",
            jwt_secret="prod-secret",
            yookassa_shop_id="shop",
            yookassa_secret_key="key",
            yookassa_webhook_secret="",
        ),
    )
    with pytest.raises(RuntimeError, match="YOOKASSA_WEBHOOK_SECRET"):
        startup_security.assert_startup_security()
