from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _default_sqlite_url() -> str:
    return f"sqlite+aiosqlite:///{(BACKEND_DIR / 'data' / 'app.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(default_factory=_default_sqlite_url)

    @field_validator("database_url", mode="after")
    @classmethod
    def sqlite_absolute_path(cls, v: str) -> str:
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

    # --- Auth / SaaS ---
    jwt_secret: str = Field(default="dev-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    fernet_key: str = Field(default="")

    public_app_url: str = Field(default="http://127.0.0.1:8080")
    # Email владельцев (через запятую), которым разрешён /api/admin без is_platform_admin в БД
    admin_emails: str = Field(default="")

    signup_bonus_credits: int = Field(default=50)
    credit_cost_inbound_translation: int = Field(default=1)
    credit_cost_outbound_translation: int = Field(default=1)

    # --- Студия: доработка промпта через OpenAI (кредиты списываются с пользователя) ---
    openai_api_key: str = Field(default="")
    # Совместимый с OpenAI прокси (например локальный) или кастомный эндпоинт: …/v1
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    # Опционально, если в кабинете OpenAI несколько org
    openai_organization: str = Field(default="")
    openai_studio_model: str = Field(default="gpt-4o-mini")
    openai_studio_model_vision: str = Field(default="gpt-4o")
    credit_cost_studio_prompt_refine: int = Field(default=2)
    image_studio_skeleton_path: str = Field(default="data/prompts/image_studio_skeleton.txt")
    image_studio_skeleton_inline: str = Field(default="")
    image_studio_system_path: str = Field(default="data/prompts/image_studio_system.txt")
    image_studio_system_inline: str = Field(default="")
    image_studio_realism_engine_path: str = Field(
        default="data/prompts/image_studio_realism_engine.json"
    )
    image_studio_realism_engine_inline: str = Field(default="")
    image_studio_reference_describe_path: str = Field(
        default="data/prompts/image_studio_reference_describe.txt"
    )
    image_studio_reference_describe_inline: str = Field(default="")
    image_studio_model_profile_gen_system_path: str = Field(
        default="data/prompts/model_profile_from_photos_system.txt",
    )
    image_studio_model_profile_gen_system_inline: str = Field(default="")
    credit_cost_studio_model_profile_generate: int = Field(default=1)

    wavespeed_api_base: str = Field(default="https://api.wavespeed.ai")
    # POST image-edit: WAN 2.7 Image Edit Pro по умолчанию; обычный WAN / Seedream — см. .env.example
    wavespeed_seedream_edit_path: str = Field(
        default="/api/v3/alibaba/wan-2.7/image-edit-pro",
    )
    # Для API Seedream v5 (jpeg | png); для WAN не используется; пусто — по умолчанию API
    wavespeed_seedream_output_format: str = Field(default="")
    # Только для WAN 2.7 Image Edit (-1 = случайный)
    wavespeed_wan_image_edit_seed: int = Field(default=-1)
    # Только для Seedream: true = дождаться результата в ответе POST. Для WAN поле в тело не попадает.
    wavespeed_seedream_sync: bool = Field(default=True)
    # True = не передавать size (как пустой размер в Playground; иначе шлём WxH из кадра студии).
    wavespeed_seedream_omit_size: bool = Field(default=False)
    # Опционально: JSON-объект, полями дополняется тело POST к WaveSpeed (для полей из DevTools Playground).
    wavespeed_extra_json: str = Field(default="")
    # Image Upscaler (док: wavespeed.ai/docs/docs-api/image-upscaler)
    wavespeed_image_upscaler_path: str = Field(
        default="/api/v3/wavespeed-ai/image-upscaler",
    )
    wavespeed_upscale_sync: bool = Field(default=True)
    credit_cost_studio_upscale: int = Field(default=1)

    stripe_secret_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")
    stripe_price_subscription: str = Field(default="")
    billing_success_path: str = "/?billing=success"
    billing_cancel_path: str = "/?billing=cancel"

    # --- Legacy single-bot polling (локальная отладка) ---
    legacy_bot_token: str = Field(
        default="",
        validation_alias=AliasChoices("LEGACY_BOT_TOKEN", "BOT_TOKEN"),
    )
    legacy_user_id: int = Field(default=0, validation_alias=AliasChoices("LEGACY_USER_ID"))
    telegram_proxy: str | None = None

    # --- Translation ---
    deepl_api_key: str | None = None
    deepl_use_free: bool = True
    libretranslate_url: str | None = None

    # Глобальный Fanvue (только обратная совместимость; в SaaS токен в БД)
    fanvue_webhook_secret: str = ""
    fanvue_access_token: str = ""
    fanvue_api_version: str = "2025-06-26"
    fanvue_api_base: str = "https://api.fanvue.com"

    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://127.0.0.1:8080,http://localhost:8080"
    )

    # Web Push (VAPID). npx web-push generate-vapid-keys
    vapid_private_key: str = Field(default="", description="PEM or raw base64 private key")
    vapid_public_key: str = Field(default="")
    vapid_sub: str = Field(
        default="",
        description="Контакт для VAPID claims, напр. mailto:ops@example.com",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def web_push_configured(self) -> bool:
        return bool(
            (self.vapid_private_key or "").strip()
            and (self.vapid_public_key or "").strip()
            and (self.vapid_sub or "").strip()
        )


settings = Settings()
