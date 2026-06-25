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

    signup_bonus_credits: int = Field(
        default=0,
        description="Кредиты при регистрации (0 — используется demo_generations_grant).",
    )
    demo_generations_grant: int = Field(
        default=3,
        ge=0,
        description="Бесплатные генерации картинок для тарифа Credits.",
    )
    demo_studio_wave_model: str = Field(
        default="nano-banana-2",
        description="Модель WaveSpeed для демо (обычные фото). NSFW в демо — wan-2.7.",
    )
    referral_signup_bonus_credits: int = Field(
        default=25,
        description="Кредиты приглашённому по реферальному коду (доп. к signup_bonus).",
    )
    referral_referrer_payment_percent: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Доля каждой оплаты приглашённого, начисляемая рефереру в кредитах (курс — billing_credits_unit_price_rub).",
    )
    marketing_beta_creators_count: int = Field(default=19)
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
    # Двухшаговый Grok (xAI): описание референс-движения → единый промпт под вашу модель + первый кадр
    studio_grok_motion_timeline_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "STUDIO_GROK_MOTION_TIMELINE_ENABLED",
            "STUDIO_GROK_MOTION_TIMELINE",
        ),
    )
    grok_api_key: str = Field(default="")
    grok_base_url: str = Field(default="https://api.x.ai/v1")
    # Пусто = взять OPENAI_STUDIO_MODEL_VISION, затем OPENAI_STUDIO_MODEL (удобно при едином xAI в OPENAI_*)
    grok_motion_model: str = Field(default="")
    grok_motion_max_seconds: int = Field(default=30, ge=4, le=120)
    grok_motion_max_frame_width: int = Field(default=768, ge=320, le=1280)
    grok_motion_send_full_video: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "GROK_MOTION_SEND_FULL_VIDEO",
            "STUDIO_GROK_MOTION_SEND_FULL_VIDEO",
        ),
    )
    grok_motion_native_video_fallback_frames: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "GROK_MOTION_NATIVE_VIDEO_FALLBACK_FRAMES",
            "GROK_MOTION_VIDEO_FALLBACK_FRAMES",
        ),
    )
    grok_motion_full_video_model: str = Field(
        default="grok-4",
        validation_alias=AliasChoices("GROK_MOTION_FULL_VIDEO_MODEL"),
    )
    grok_motion_xai_upload_max_bytes: int = Field(
        default=45 * 1024 * 1024,
        ge=5 * 1024 * 1024,
        le=50 * 1024 * 1024 - 4096,
    )
    grok_motion_full_video_timeout_seconds: float = Field(default=900.0, ge=60.0, le=2700.0)
    grok_scene_compose_system_path: str = Field(
        default="data/prompts/grok_scene_compose_system.txt"
    )
    grok_scene_compose_text_system_path: str = Field(
        default="data/prompts/grok_scene_compose_text_system.txt"
    )
    grok_scene_compose_model_scene_system_path: str = Field(
        default="data/prompts/grok_scene_compose_model_scene_system.txt"
    )
    grok_scene_compose_main_system_path: str = Field(
        default="data/prompts/grok_scene_compose_main_system.txt"
    )
    grok_scene_compose_main_system_inline: str = Field(default="")
    grok_scene_compose_output_max_chars: int = Field(default=3000, ge=800, le=5000)
    grok_scene_compose_system_inline: str = Field(default="")
    grok_scene_compose_text_system_inline: str = Field(default="")
    grok_scene_compose_model: str = Field(default="")
    grok_scene_compose_max_tokens: int = Field(default=8192, ge=1024, le=16384)
    grok_scene_compose_temperature: float = Field(default=0.45, ge=0.0, le=1.5)
    grok_scene_compose_timeout_seconds: float = Field(default=180.0, ge=30.0, le=600.0)
    # Seedance T2V: макс. длина финального промпта (символов) после Grok / сборки
    studio_seedance_t2v_prompt_max_chars: int = Field(default=3000, ge=500, le=5000)
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
    image_studio_reference_describe_no_face_path: str = Field(
        default="data/prompts/image_studio_reference_describe_no_face.txt"
    )
    motion_first_frame_scene_describe_path: str = Field(
        default="data/prompts/motion_first_frame_scene_describe.txt",
    )
    motion_first_frame_scene_describe_inline: str = Field(default="")
    image_studio_model_profile_gen_system_path: str = Field(
        default="data/prompts/model_profile_from_photos_system.txt",
    )
    image_studio_model_profile_gen_system_inline: str = Field(default="")
    image_studio_model_profile_template_path: str = Field(
        default="data/prompts/model_profile_template.json",
    )
    credit_cost_studio_model_profile_generate: int = Field(default=1)
    # Локальная отладка: клиент может передать generate_wavespeed=0 и получить только refined_prompt без WaveSpeed
    studio_allow_prompt_only: bool = Field(default=False)
    credit_cost_studio_carousel_shot: int = Field(default=2)
    # Архив студии (файлы + БД): автоудаление записей старше N дней; 0 = отключено
    studio_generations_retention_days: int = Field(default=4, ge=0)
    studio_generations_retention_interval_hours: int = Field(default=24, ge=1)
    # Скачивание готового кадра с CDN провайдера в архив студии (повторы при обрыве/таймауте).
    studio_archive_download_attempts: int = Field(default=6, ge=1, le=15)
    studio_archive_download_timeout_seconds: float = Field(default=300.0, ge=30.0, le=600.0)
    # Фоновый догруз архива для записей provider_ready без файла на диске
    studio_archive_retry_interval_seconds: int = Field(default=300, ge=60, le=3600)
    studio_archive_retry_batch_size: int = Field(default=20, ge=1, le=100)
    # Перед phone EXIF: снять C2PA / XMP «Made with AI» / AI EXIF (remove-ai-watermarks, CPU).
    studio_strip_ai_metadata_enabled: bool = Field(default=True)
    # Analog Humanizer: film grain + хроматика против пиксельных AI-классификаторов (CPU).
    studio_analog_humanize_enabled: bool = Field(default=True)
    studio_analog_humanize_grain: float = Field(default=2.5, ge=0.0, le=12.0)
    studio_analog_humanize_chromatic_shift: int = Field(default=1, ge=0, le=4)
    # Множитель grain_sigma в phone EXIF; при уже применённом humanize grain не дублируется.
    studio_phone_export_grain_multiplier: float = Field(default=1.15, ge=1.0, le=3.0)
    studio_phone_export_jpeg_quality: int = Field(default=88, ge=75, le=95)
    # Архив видео: phone Make/Model/Lens/GPS/дата и снятие C2PA/XMP без перекодирования (exiftool).
    studio_video_phone_export_enabled: bool = Field(default=True)
    studio_video_metadata_exiftool_timeout_seconds: float = Field(default=180.0, ge=30.0, le=600.0)
    studio_generation_stale_processing_hours: int = Field(default=48, ge=1, le=96)
    # Опрос Seedance / video на бэкенде: 800 × 3 с ≈ 40 мин (клиент не долбит API).
    wavespeed_video_max_polls: int = Field(default=800, ge=60, le=1200)
    wavespeed_video_poll_interval_seconds: float = Field(default=3.0, ge=1.0, le=15.0)

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
    # Студия «видео»: только ByteDance Seedance 2.0 Text-to-Video
    # https://wavespeed.ai/models/bytedance/seedance-2.0/text-to-video
    wavespeed_seedance_20_t2v_path: str = Field(
        default="/api/v3/bytedance/seedance-2.0/text-to-video",
    )
    # Seedance 2.0 Mini T2V (легче/дешевле; см. wavespeed.ai/docs …/seedance-2.0-mini-text-to-video)
    wavespeed_seedance_20_mini_t2v_path: str = Field(
        default="/api/v3/bytedance/seedance-2.0-mini/text-to-video",
    )
    wavespeed_seedance_20_t2v_resolution: str = Field(default="720p")
    # WaveSpeed Seedance T2V принимает duration только 4–15 с (см. доки API).
    studio_motion_video_duration_min: int = Field(default=4, ge=4, le=15)
    studio_motion_video_duration_max: int = Field(default=15, ge=1, le=60)
    wavespeed_seedance_20_t2v_duration: int = Field(default=5, ge=1, le=15)
    wavespeed_seedance_20_t2v_web_search: bool = Field(default=False)
    # Видео Seedance T2V: USD/сек при 720p → кредиты через STUDIO_MOTION_RUB_PER_USD и STUDIO_MOTION_RUB_PER_CREDIT
    # Standard 720p: WaveSpeed docs ≈ $0.24/с без реф-видео, $0.15/с с реф-видео (упрощённо по output duration)
    studio_motion_usd_per_sec_with_ref: float = Field(default=0.50, ge=0.0)
    studio_motion_usd_per_sec_no_ref: float = Field(default=0.25, ge=0.0)
    # Mini 720p: ориентир ~75% от Seedance 2.0 Fast (официальный прайс Mini — в env после релиза)
    studio_motion_mini_usd_per_sec_with_ref: float = Field(default=0.0975, ge=0.0)
    studio_motion_mini_usd_per_sec_no_ref: float = Field(default=0.15, ge=0.0)
    studio_motion_rub_per_usd: float = Field(default=80.0, ge=0.01)
    studio_motion_rub_per_credit: float = Field(default=3.6, ge=0.01)
    # Устарело: заменено динамическим расчётом; оставлено для совместимости .env
    credit_cost_studio_motion_control: int = Field(default=10, ge=0)
    # Legacy (не используется рендером видео; оставлено для совместимости .env)
    studio_motion_video_provider: str = Field(default="seedance_t2v")
    wavespeed_kling_motion_control_path: str = Field(
        default="/api/v3/kwaivgi/kling-v3.0-pro/motion-control",
    )
    wavespeed_kling_motion_sync: bool = Field(default=True)
    wavespeed_wan_22_animate_path: str = Field(
        default="/api/v3/wavespeed-ai/wan-2.2/animate",
    )
    wavespeed_wan_22_animate_mode: str = Field(default="replace")
    wavespeed_wan_22_animate_resolution: str = Field(default="720p")
    wavespeed_wan_22_animate_seed: int = Field(default=-1)
    wavespeed_seedance_20_i2v_path: str = Field(
        default="/api/v3/bytedance/seedance-2.0/image-to-video",
    )
    wavespeed_seedance_20_i2v_resolution: str = Field(default="720p")
    wavespeed_seedance_20_i2v_duration: int = Field(default=5, ge=1, le=15)
    wavespeed_seedance_20_i2v_web_search: bool = Field(default=False)
    # Опционально: ByteDance Seedance Fast Video-Edit (не используется шагом рендера по умолчанию)
    wavespeed_studio_video_edit_path: str = Field(
        default="/api/v3/bytedance/seedance-2.0-fast/video-edit-turbo",
    )
    # 720p | 1080p (см. доки turbo)
    wavespeed_studio_video_edit_resolution: str = Field(default="720p")
    # Максимальный размер загружаемого driving video (MP4/WebM/MOV) для студии «видео по референсу»
    studio_motion_max_upload_mb: int = Field(default=64, ge=1, le=200)
    # Имя или абсолютный путь к ffmpeg (в официальном Docker-образе — /usr/bin/ffmpeg)
    ffmpeg_binary: str = Field(default="ffmpeg")
    # exiftool для метаданных видео (в Docker: libimage-exiftool-perl → /usr/bin/exiftool)
    exiftool_binary: str = Field(default="exiftool")
    # Режим «Обычные фотографии»: та же учётка WaveSpeed, что и WAN — см. модель
    # https://wavespeed.ai/models/google/nano-banana-pro/edit и API /api/v3/google/nano-banana-pro/edit
    wavespeed_nano_banana_pro_edit_path: str = Field(
        default="/api/v3/google/nano-banana-pro/edit",
    )
    wavespeed_nano_banana_pro_resolution: str = Field(default="2k")
    wavespeed_nano_banana_pro_sync: bool = Field(default=False)
    wavespeed_nano_banana_pro_output_format: str = Field(default="png")
    # Google Nano Banana часто отвечает «check your input parameters» на слишком длинный prompt
    wavespeed_nano_prompt_max_chars: int = Field(default=12000, ge=2000, le=32000)
    # Z-Image Turbo Inpaint (маска: белое — редактировать, чёрное — сохранить)
    # https://wavespeed.ai/docs/docs-api/wavespeed-ai/z-image-turbo-inpaint
    wavespeed_z_image_inpaint_path: str = Field(
        default="/api/v3/wavespeed-ai/z-image/turbo-inpaint",
    )
    # True = не передавать size (размер остаётся как у входного изображения).
    wavespeed_z_image_inpaint_omit_size: bool = Field(default=True)
    credit_cost_studio_inpaint: int = Field(default=2)
    # Маска студии в Nano/WAN: см. studio_routes + STUDIO_MASKED_FULLFRAME_*.
    # False = только Z-Image Turbo Inpaint (полное поле mask_image этого API).
    studio_regional_masked_edit: bool = Field(default=True)
    studio_regional_masked_edit_pad_ratio: float = Field(default=0.14, ge=0.03, le=0.42)
    studio_regional_masked_min_crop_side_px: int = Field(default=384, ge=128, le=4096)
    studio_regional_masked_feather_radius: float = Field(default=5.5, ge=0.0, le=36.0)
    studio_regional_masked_harmonize_ring_thresh: float = Field(
        default=0.16, ge=0.04, le=0.45
    )
    studio_regional_masked_mask_threshold: int = Field(default=100, ge=16, le=240)
    studio_masked_fullframe_preserve_unmasked: bool = Field(
        default=True,
        description="После Nano/WAN с маской как вторым URL смешать ответ провайдера с исходником "
        "(пиксели вне смягчённой маски = как в загруженном фото).",
    )
    studio_masked_fullframe_blend_feather_radius: float = Field(
        default=10.0,
        ge=0.0,
        le=64.0,
        description="Радиус GaussianBlur маски альфы перед смешением (меньше = жёстче шов).",
    )

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
        "grok_api_key",
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
    billing_credits_unit_price_rub: Decimal = Field(
        default=Decimal("3.7"),
        description="1 кредит = N ₽ (оплата подписки кредитами, реферальный пересчёт, докупка до bulk_from).",
    )
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

    @field_validator("studio_motion_video_provider", mode="after")
    @classmethod
    def _normalize_motion_video_provider(cls, v: str) -> str:
        return "seedance_t2v"

    @field_validator("wavespeed_seedance_20_t2v_resolution", mode="after")
    @classmethod
    def _seedance_t2v_resolution(cls, v: str) -> str:
        s = (v or "720p").strip().lower()
        return s if s in ("480p", "720p", "1080p") else "720p"

    @field_validator("wavespeed_seedance_20_i2v_resolution", mode="after")
    @classmethod
    def _seedance_i2v_resolution(cls, v: str) -> str:
        s = (v or "720p").strip().lower()
        return s if s in ("480p", "720p", "1080p") else "720p"

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

    # --- Email / SMTP (свой Postfix на VPS или relay: Yandex, Mailgun, SendGrid…) ---
    smtp_host: str = Field(default="", description="SMTP-сервер, напр. localhost или smtp.yandex.ru")
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from_email: str = Field(default="", description="From: hello@modelmate.ru")
    smtp_from_name: str = Field(default="ModelMate")
    smtp_use_tls: bool = Field(default=True, description="STARTTLS (порт 587)")
    smtp_use_ssl: bool = Field(default=False, description="SSL с самого начала (порт 465)")
    email_campaign_batch_size: int = Field(default=25, ge=1, le=200)
    email_campaign_batch_delay_seconds: float = Field(default=2.0, ge=0.0, le=60.0)

    @field_validator(
        "smtp_host",
        "smtp_user",
        "smtp_password",
        "smtp_from_email",
        mode="after",
    )
    @classmethod
    def _strip_smtp_fields(cls, v: str) -> str:
        return (v or "").strip()

    @property
    def smtp_configured(self) -> bool:
        return bool((self.smtp_host or "").strip() and (self.smtp_from_email or "").strip())


settings = Settings()
