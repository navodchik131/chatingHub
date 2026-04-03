from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import make_url

# Каталог backend (где лежит app/) — пути к SQLite не зависят от текущей рабочей директории
BACKEND_DIR = Path(__file__).resolve().parent.parent


def _default_sqlite_url() -> str:
    return f"sqlite+aiosqlite:///{(BACKEND_DIR / 'data' / 'app.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = ""
    # HTTP(S) или SOCKS5 прокси до api.telegram.org (если прямой доступ блокируется)
    # Пример: http://127.0.0.1:7890 или socks5://127.0.0.1:1080
    telegram_proxy: str | None = None
    database_url: str = Field(default_factory=_default_sqlite_url)

    @field_validator("database_url", mode="after")
    @classmethod
    def sqlite_absolute_path(cls, v: str) -> str:
        """Относительные sqlite-пути привязываем к каталогу backend (не к cwd)."""
        if not v.startswith("sqlite+aiosqlite"):
            return v
        u = make_url(v)
        if not u.database:
            return v
        p = Path(u.database)
        if not p.is_absolute():
            p = (BACKEND_DIR / p).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{p.as_posix()}"
    # DeepL: https://www.deepl.com/pro-api — free tier uses api-free.deepl.com
    deepl_api_key: str | None = None
    deepl_use_free: bool = True
    # Если DeepL нет — можно задать URL LibreTranslate (свой инстанс)
    libretranslate_url: str | None = None

    # Fanvue: https://api.fanvue.com/docs — вебхук + отправка в чат (OAuth Bearer)
    fanvue_webhook_secret: str = ""
    fanvue_access_token: str = ""
    fanvue_api_version: str = "2025-06-26"
    fanvue_api_base: str = "https://api.fanvue.com"

    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://127.0.0.1:8080,http://localhost:8080"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
