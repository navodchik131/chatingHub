from decimal import Decimal
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
    image_studio_reference_describe_match_pose_hair_path: str = Field(
        default="data/prompts/image_studio_reference_describe_match_pose_hair.txt"
    )
    image_studio_model_profile_gen_system_path: str = Field(
        default="data/prompts/model_profile_from_photos_system.txt",
    )
    image_studio_model_profile_gen_system_inline: str = Field(default="")
    credit_cost_studio_model_profile_generate: int = Field(default=1)
    # Локальная отладка: клиент может передать generate_wavespeed=0 и получить только refined_prompt без WaveSpeed
    studio_allow_prompt_only: bool = Field(default=False)
    credit_cost_studio_carousel_shot: int = Field(default=2)
    # Архив студии (файлы + БД): автоудаление записей старше N дней; 0 = отключено
    studio_generations_retention_days: int = Field(default=4, ge=0)
    studio_generations_retention_interval_hours: int = Field(default=24, ge=1)

    wavespeed_api_base: str = Field(default="https://api.wavespeed.ai")
    # POST image-edit: WAN 2.7 по умолчанию; Pro / Seedream — см. .env.example
    wavespeed_seedream_edit_path: str = Field(
        default="/api/v3/alibaba/wan-2.7/image-edit",
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
    # Kling Motion Control: перенос движения с референс-видео на утверждённый кадр модели
    wavespeed_kling_motion_control_path: str = Field(
        default="/api/v3/kwaivgi/kling-v3.0-pro/motion-control",
    )
    wavespeed_kling_motion_sync: bool = Field(default=True)
    credit_cost_studio_motion_control: int = Field(default=10, ge=0)
    # Максимальный размер загружаемого driving video (MP4/WebM/MOV) для студии «видео по референсу»
    studio_motion_max_upload_mb: int = Field(default=64, ge=1, le=200)
    # Имя или абсолютный путь к ffmpeg (в официальном Docker-образе — /usr/bin/ffmpeg)
    ffmpeg_binary: str = Field(default="ffmpeg")
    # Режим «Обычные фотографии»: та же учётка WaveSpeed, что и WAN — см. модель
    # https://wavespeed.ai/models/google/nano-banana-pro/edit и API /api/v3/google/nano-banana-pro/edit
    wavespeed_nano_banana_pro_edit_path: str = Field(
        default="/api/v3/google/nano-banana-pro/edit",
    )
    wavespeed_nano_banana_pro_resolution: str = Field(default="2k")
    wavespeed_nano_banana_pro_sync: bool = Field(default=True)
    wavespeed_nano_banana_pro_output_format: str = Field(default="png")

    billing_success_path: str = "/?billing=success"

    # --- YooKassa (платежи в RUB) — shop_id и secret из личного кабинета ---
    yookassa_shop_id: str = Field(default="")
    yookassa_secret_key: str = Field(default="")
    yookassa_webhook_secret: str = Field(
        default="",
        description="Опционально: проверка входящих уведомлений ЮKassa",
    )

    # Ключ WaveSpeed платформы для тарифа Managed (студия: генерация, апскейл, карусель).
    # При BYOK используется ключ из кабинета «Интеграции».
    wavespeed_platform_api_key: str = Field(
        default="",
        description="API-ключ WaveSpeed из .env для подписчиков Managed (студия). BYOK — ключ владельца в БД.",
    )

    @field_validator(
        "wavespeed_platform_api_key",
        "openai_api_key",
        "yookassa_shop_id",
        "yookassa_secret_key",
        mode="after",
    )
    @classmethod
    def _strip_optional_secrets(cls, v: str) -> str:
        return (v or "").strip()

    # Требовать активную подписку для студии (и не истёкший оплаченный период, если задан)
    billing_require_active_subscription: bool = Field(default=True)
    # Пока ЮKassa не настроена (shop_id + secret пусты): автоматически выдавать владельцам
    # активную подписку Managed (платформенный OPENAI_* из .env).
    # После подключения оплаты режим сам отключается (см. starter_plan.starter_managed_effective).
    billing_auto_starter_managed_without_payment: bool = Field(default=True)

    # Цены в рублях (целые); в ЮKassa передаём как "499.00"
    billing_price_byok_month_rub: int = Field(default=499)
    billing_price_managed_month_rub: int = Field(default=1299)
    billing_managed_subscription_bonus_credits: int = Field(
        default=250,
        description="Кредиты на баланс при успешной оплате подписки Managed (каждый платёж sub_managed_month).",
    )
    billing_credit_pack_credits: int = Field(default=100)
    billing_credit_pack_price_rub: int = Field(default=990)
    # Покупка кредитов: произвольное количество (старый фиксированный пакет — только для совместимости вебхуков)
    billing_credits_min_purchase: int = Field(default=50)
    billing_credits_bulk_from: int = Field(default=200)
    billing_credits_unit_price_rub: Decimal = Field(default=Decimal("3"))
    billing_credits_bulk_unit_price_rub: Decimal = Field(default=Decimal("2.70"))
    billing_credits_max_purchase: int = Field(default=500_000)
    billing_subscription_period_days: int = Field(default=30)

    @property
    def yookassa_configured(self) -> bool:
        return bool((self.yookassa_shop_id or "").strip() and (self.yookassa_secret_key or "").strip())

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
