from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.config import settings
from app.db.models import MessageDirection, Platform


class MessageAttachmentOut(BaseModel):
    id: int
    kind: str
    url: str
    mime_type: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    direction: MessageDirection
    text_original: str
    text_translated: str | None
    created_at: datetime
    attachments: list[MessageAttachmentOut] = []
    reply_to_message_id: int | None = None
    reply_preview: str | None = None
    reactions: list[MessageReactionOut] = Field(default_factory=list)
    companion_bot: bool = False
    bot_response_event_id: int | None = None
    operator_rating: int | None = None
    """False если реакция сохранена локально, но Telegram не принял sync."""
    platform_sync_ok: bool | None = None


class CompanionDraftOut(BaseModel):
    id: int
    conversation_id: int
    trigger_message_id: int
    draft_text: str
    target_lang: str | None = None
    created_at: datetime


class CompanionDraftApproveIn(BaseModel):
    text: str | None = None


class CompanionRatingIn(BaseModel):
    rating: Literal[-1, 0, 1]


class CompanionFeedbackReportOut(BaseModel):
    id: int
    report_date: datetime
    content: str
    stats: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CompanionStyleIndexStatsOut(BaseModel):
    owners: int = 0
    conversations_scanned: int = 0
    pairs_found: int = 0
    pairs_added: int = 0
    pairs_trimmed: int = 0


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: Platform
    external_chat_id: str
    external_topic_id: str
    user_display_name: str | None
    user_lang: str | None
    """Если задан — ответы переводим в этот язык; иначе по user_lang (детекция с последних входящих)."""
    outbound_lang: str | None = None
    """Модель студии для доступа операторов; только владелец назначает."""
    studio_model_id: int | None = None
    """Не переводить входящие/исходящие — только оригинальный текст."""
    auto_translate_disabled: bool = False
    """NULL = режим с подключения; off/draft/semi_auto/auto — переопределение."""
    companion_mode_override: str | None = None
    """Фактический режим с учётом подключения (off/draft/semi_auto/auto)."""
    effective_companion_mode: str | None = None
    """Ручная категория: vip, bomzh или NULL."""
    manual_category: Literal["vip", "bomzh"] | None = None
    is_blocked: bool = False
    peer_unavailable: bool = False
    is_hidden: bool = False
    assigned_user_id: int | None = None
    assigned_member_login: str | None = None
    updated_at: datetime
    has_avatar: bool = False


class ConversationWithPreview(ConversationOut):
    last_message_preview: str | None = None
    unread_count: int = 0
    is_no_response: bool = False
    is_new: bool = False


class ReplyIn(BaseModel):
    text: str
    reply_to_message_id: int | None = None


class MessageReactionOut(BaseModel):
    emoji: str
    actor: Literal["owner", "peer"]


class MessageReactionIn(BaseModel):
    emoji: str = Field(min_length=1, max_length=32)


class ConversationPatchIn(BaseModel):
    """Частичное обновление диалога (язык исходящих, перевод, модель, категория)."""

    outbound_lang: str | None = None
    studio_model_id: int | None = None
    auto_translate_disabled: bool | None = None
    companion_mode_override: Literal["off", "draft", "semi_auto", "auto"] | None = None
    manual_category: Literal["vip", "bomzh"] | None = None
    is_blocked: bool | None = None
    assigned_user_id: int | None = None

    @field_validator("manual_category", mode="before")
    @classmethod
    def _strip_manual_category(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            return None
        s = v.strip().lower()
        if not s or s in ("none", "null", ""):
            return None
        return s

    @field_validator("companion_mode_override", mode="before")
    @classmethod
    def _strip_companion_override(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            return None
        s = v.strip().lower()
        if not s or s == "inherit":
            return None
        return s

    @field_validator("outbound_lang", mode="before")
    @classmethod
    def _strip_outbound_lang(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            return None
        s = v.strip()
        return s if s else None


class ConversationNoteOut(BaseModel):
    id: int
    kind: Literal["manual", "ai_profile", "ai_daily", "ai_insight"]
    content: str
    is_pinned: bool
    author_user_id: int | None = None
    author_label: str
    created_at: datetime
    updated_at: datetime


class ConversationNoteCreateIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    is_pinned: bool = False


class ConversationNotePatchIn(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=8000)
    is_pinned: bool | None = None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    referral_code: str | None = Field(default=None, max_length=16)


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    """Логин сотрудника внутри пространства (вместе с email владельца)."""
    member_login: str | None = None


class TelegramLoginIn(BaseModel):
    id: int = Field(gt=0)
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int = Field(gt=0)
    hash: str = Field(min_length=1)


class CompleteOwnerEmailIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PlanLimitsOut(BaseModel):
    max_users: int
    max_models: int
    max_dialogs_per_month: int | None = None
    max_grok_per_month: int | None = None


class PlanUsageOut(BaseModel):
    users: int
    models: int
    dialogs_this_month: int
    grok_this_month: int
    limits: PlanLimitsOut


class UserMeOut(BaseModel):
    id: int
    email: str
    subscription_status: str
    credits_balance: int
    """План биллинга: credits | standard | pro."""
    billing_plan: str = "standard"
    """solo | pro | studio."""
    plan_tier: str = "solo"
    plan_display_name: str = "Credits"
    plan_usage: PlanUsageOut | None = None
    """Дата окончания оплаченного периода подписки (UTC), если есть."""
    subscription_period_end: datetime | None = None
    """Число подключённых операторов (участников), не считая владельца."""
    operators_count: int = 0
    is_workspace_owner: bool = True
    is_platform_admin: bool = False
    workspace_owner_id: int
    member_login: str | None = None
    permissions_mask: int = 0
    owner_email: str
    billing_require_active_subscription: bool = True
    """Можно оформить или продлить подписку онлайн (на сервере настроена оплата)."""
    online_payment_available: bool = False
    signup_bonus_credits: int = 0
    demo_generations_remaining: int = 0
    demo_generations_grant: int = 3
    """Чаты и диалоги доступны (Standard / Pro; не Credits без оплаченной подписки)."""
    chat_allowed: bool = False
    """Credits с демо без купленных кредитов — только workflow «По рефу»."""
    workflow_demo_limited: bool = False
    telegram_linked: bool = False
    telegram_username: str | None = None
    """Владелец: нужно указать рабочий email (после входа через Telegram)."""
    email_setup_required: bool = False
    """Email для отображения; пусто, если аккаунт только через Telegram."""
    public_email: str | None = None
    telegram_login_available: bool = False
    tribute_billing_available: bool = False


class WorkspaceMemberCreateIn(BaseModel):
    member_login: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    permissions_mask: int | None = None
    """Пустой список — участник без моделей, пока владелец не назначит."""
    allowed_studio_model_ids: list[int] = Field(default_factory=list)
    tribute_share_percent: int | None = Field(default=None, ge=0, le=100)


class WorkspaceMemberPatchIn(BaseModel):
    permissions_mask: int | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None
    allowed_studio_model_ids: list[int] | None = None
    tribute_share_percent: int | None = Field(default=None, ge=0, le=100)


class WorkspaceMemberOut(BaseModel):
    id: int
    member_login: str
    permissions_mask: int
    is_active: bool
    allowed_studio_model_ids: list[int] = Field(default_factory=list)
    tribute_share_percent: int


class CreditHistoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    kind: str
    credits_delta: int


class CreditHistoryPageOut(BaseModel):
    items: list[CreditHistoryItemOut]
    has_more: bool


class StudioRefinePromptOut(BaseModel):
    """Результат refine: текст, URL картинки; generation_id — запись в архиве на диске, если успели сохранить."""

    refined_prompt: str
    reference_scene_description: str | None = None
    reference_analysis: dict[str, Any] | None = None
    generated_image_url: str | None = None
    wavespeed_message: str | None = None
    generation_id: int | None = None


class StudioReferenceAnalysisOut(BaseModel):
    analysis: dict[str, Any]
    summary_ru: str
    effective_studio_mode: str
    visibility: dict[str, Any]


class StudioImportArchiveImageIn(BaseModel):
    """Повторная загрузка в архив по временному HTTPS URL (например с CDN после сбоя скачивания на сервер)."""

    source_url: str = Field(..., max_length=2048)
    generation_id: int | None = Field(
        default=None,
        ge=1,
        description="Существующая запись provider_ready — догрузить файл без новой строки в БД",
    )
    refined_prompt: str | None = Field(default=None, max_length=65536)
    output_aspect: str | None = Field(default=None, max_length=48)
    studio_model_id: int | None = Field(default=None, ge=1)
    exif_camera: str | None = Field(
        default=None,
        description="EXIF при сохранении: selfie (фронталка) или main (основная камера)",
    )


class StudioImportArchiveImageOut(BaseModel):
    generated_image_url: str | None = None
    generation_id: int | None = None
    message: str | None = None


class StudioModelBootstrapOut(BaseModel):
    """Результат шага «База модели»: слияние лиц или развёртка."""

    refined_prompt: str
    generated_image_url: str | None = None
    generation_id: int | None = None
    wavespeed_message: str | None = None


class StudioMotionFirstFrameOut(BaseModel):
    """Шаг 1: первый кадр видео детально разбирается (без личности/оверлеев); опционально — сводка движения по клипу."""

    refined_prompt: str
    reference_scene_description: str | None = None
    motion_video_prompt_auto: str | None = None
    generated_image_url: str | None = None
    wavespeed_message: str | None = None
    generation_id: int | None = None
    motion_video_file_id: str | None = None


class StudioMotionComposeVideoPromptOut(BaseModel):
    """Grok: timeline движения по реф-видео + кадр модели (без генерации картинки)."""

    motion_video_prompt_auto: str
    reference_scene_description: str | None = None
    generation_id: int | None = None
    motion_video_file_id: str | None = None
    message: str | None = None


class StudioMotionVideoOut(BaseModel):
    """Шаг 2: референс-видео + кадр модели → WAN 2.2 Animate (replace / animate)."""

    video_url: str | None = None
    message: str | None = None
    motion_video_prompt_auto: str | None = None


class StudioJobAcceptedOut(BaseModel):
    job_id: int
    status: str = "pending"
    job_type: str
    generation_id: int | None = None
    message: str = "Задача принята. Ожидайте результат — статус обновится автоматически."


class StudioJobStatusOut(BaseModel):
    job_id: int
    job_type: str
    status: str
    error_message: str | None = None
    result: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class StudioMotionDrivingVideoUploadOut(BaseModel):
    motion_video_file_id: str


class StudioMotionRenderOut(BaseModel):
    id: int
    created_at: datetime
    studio_generation_id: int | None = None
    studio_model_id: int | None = None
    video_url: str
    frame_image_url: str


class StudioMotionRendersPageOut(BaseModel):
    items: list[StudioMotionRenderOut]
    has_more: bool


class StudioUpscaleGenerationIn(BaseModel):
    """Опционально: целевое разрешение апскейла WaveSpeed Image Upscaler."""

    target_resolution: Literal["2k", "4k", "8k"] | None = None


class StudioUpscaleGenerationOut(BaseModel):
    """Новая запись архива после апскейла; исходный gen_id в ответе не дублируем — клиент знает из URL."""

    generated_image_url: str | None = None
    generation_id: int | None = None
    message: str | None = None
    target_resolution: str


class StudioCarouselIn(BaseModel):
    """Несколько кадров той же сцены / той же модели по мастер-генерации (для карусели в соцсетях)."""

    count: int = Field(default=4, ge=1, le=5)
    studio_wave_profile: Literal["regular", "nsfw"] = "nsfw"
    wan_edit_tier: Literal["standard", "pro"] = "standard"


class StudioCarouselItemOut(BaseModel):
    generation_id: int
    image_url: str


class StudioCarouselOut(BaseModel):
    items: list[StudioCarouselItemOut] = Field(default_factory=list)
    message: str | None = None


class StudioGenerationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    output_aspect: str | None = None
    studio_model_id: int | None = None
    model_name: str | None = None
    prompt_excerpt: str | None = None
    status: str = "ready"
    media_kind: Literal["image", "video"] = "image"
    error_message: str | None = None
    job_id: int | None = None
    image_url: str = ""
    video_url: str | None = None


class StudioGenerationsPageOut(BaseModel):
    items: list[StudioGenerationOut]
    has_more: bool


class StudioGenerationsPendingOut(BaseModel):
    """Только незавершённые записи архива — для редкого опроса клиента."""

    items: list[StudioGenerationOut]
    poll_after_seconds: int = 12


class WavespeedIntegrationIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=512)

    @field_validator("api_key", mode="before")
    @classmethod
    def strip_key(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()


class LlmIntegrationIn(BaseModel):
    """OpenAI-совместимый API для студии (тариф BYOK)."""

    api_key: str = Field(min_length=8, max_length=512)
    base_url: str | None = Field(
        default=None,
        max_length=512,
        description="База до /v1, например https://api.openai.com/v1 или прокси",
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def strip_llm_key(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("base_url", mode="before")
    @classmethod
    def strip_base_url(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


class StudioModelImageOut(BaseModel):
    id: int
    url: str
    kind: str = "other"


class StudioModelImagePatchIn(BaseModel):
    kind: str | None = Field(default=None, min_length=1, max_length=24)


class StudioCameraPresetOut(BaseModel):
    id: str
    label: str


class PhoneExifReferenceOut(BaseModel):
    role: str
    ready: bool
    summary: str | None = None


class CompanionPersonaOut(BaseModel):
    age: str | None = None
    city: str | None = None
    country: str | None = None
    timezone: str | None = None
    personality: str | None = None
    hobbies: str | None = None
    interests: str | None = None
    lifestyle: str | None = None
    speaking_style: str | None = None
    backstory: str | None = None


class CompanionPersonaIn(BaseModel):
    age: str | None = Field(default=None, max_length=32)
    city: str | None = Field(default=None, max_length=128)
    country: str | None = Field(default=None, max_length=128)
    timezone: str | None = Field(default=None, max_length=64)
    personality: str | None = Field(default=None, max_length=2000)
    hobbies: str | None = Field(default=None, max_length=2000)
    interests: str | None = Field(default=None, max_length=2000)
    lifestyle: str | None = Field(default=None, max_length=2000)
    speaking_style: str | None = Field(default=None, max_length=1000)
    backstory: str | None = Field(default=None, max_length=4000)


class UserStudioModelOut(BaseModel):
    id: int
    name: str
    profile_text: str
    companion_persona: CompanionPersonaOut = Field(default_factory=CompanionPersonaOut)
    image_count: int = 0
    images: list[StudioModelImageOut] = Field(default_factory=list)
    camera_preset_id: str | None = None
    export_lat: float | None = None
    export_lon: float | None = None
    phone_exif_selfie_ready: bool = False
    phone_exif_main_ready: bool = False
    phone_exif_selfie_summary: str | None = None
    phone_exif_main_summary: str | None = None


class UserStudioModelPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    profile_text: str | None = None
    companion_persona: CompanionPersonaIn | None = None
    camera_preset_id: str | None = Field(default=None, max_length=64)
    export_lat: float | None = None
    export_lon: float | None = None


class StudioModelProfileGenerateOut(BaseModel):
    """JSON-текст для поля описания модели (внешность / model_profile)."""

    profile_text: str


class TelegramIntegrationIn(BaseModel):
    """Токен BotFather, формат `числа:строка` (обычно ~45+ символов)."""

    bot_token: str = Field(min_length=15, max_length=512)
    label: str | None = Field(default=None, max_length=128)
    studio_model_id: int | None = Field(default=None, ge=1)
    connection_id: int | None = Field(default=None, ge=1)

    @field_validator("bot_token", mode="before")
    @classmethod
    def strip_bot_token(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()


class FanvueIntegrationIn(BaseModel):
    access_token: str = Field(min_length=10)
    creator_uuid: str = Field(min_length=8, max_length=64)
    webhook_signing_secret: str | None = Field(default=None, max_length=512)


class FanvueOAuthStartIn(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    studio_model_id: int | None = Field(default=None, ge=1)
    connection_id: int | None = Field(default=None, ge=1)


class FanvueOAuthStartOut(BaseModel):
    authorize_url: str


class InstagramOAuthStartIn(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    studio_model_id: int | None = Field(default=None, ge=1)
    connection_id: int | None = Field(default=None, ge=1)


class InstagramOAuthStartOut(BaseModel):
    authorize_url: str


class PlatformConnectionPatchIn(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    studio_model_id: int | None = Field(default=None, ge=1)
    companion_mode: Literal["off", "draft", "semi_auto", "auto"] | None = None
    companion_delay_min_sec: int | None = Field(default=None, ge=0, le=300)
    companion_delay_max_sec: int | None = Field(default=None, ge=0, le=600)
    companion_max_replies_per_hour: int | None = Field(default=None, ge=1, le=500)


class PlatformConnectionOut(BaseModel):
    id: int
    platform: Literal["telegram", "fanvue", "instagram", "tribute"]
    label: str | None = None
    studio_model_id: int | None = None
    bot_username: str | None = None
    webhook_registered: bool = False
    creator_uuid: str | None = None
    instagram_user_id: str | None = None
    instagram_username: str | None = None
    oauth_connected: bool = False
    webhook_url: str | None = None
    is_active: bool = True
    companion_mode: str = "off"
    companion_delay_min_sec: int = 5
    companion_delay_max_sec: int = 45
    companion_max_replies_per_hour: int = 60


class TributeIntegrationIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=512)
    label: str | None = Field(default=None, max_length=128)
    studio_model_id: int | None = Field(default=None, ge=1)
    connection_id: int | None = Field(default=None, ge=1)


class TributeEarningsSummaryOut(BaseModel):
    from_date: date
    to_date: date
    is_owner: bool
    chatter_share_percent: int
    gross_minor: int
    display_minor: int
    currency: str
    by_currency: dict[str, int] = Field(default_factory=dict)
    gross_by_currency: dict[str, int] = Field(default_factory=dict)
    event_count: int = 0


class CreatorDonationLinkIn(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    button_text: str | None = Field(default=None, max_length=64)
    cover_image_url: str | None = Field(default=None, max_length=2048)
    currency: Literal["EUR", "RUB", "USD"]
    min_amount_minor: int | None = Field(default=None, ge=1)
    allow_one_time: bool = True
    allow_recurring: bool = True
    studio_model_id: int | None = Field(default=None, ge=1)
    submit: bool = False


class CreatorDonationLinkPatchIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    button_text: str | None = Field(default=None, max_length=64)
    cover_image_url: str | None = Field(default=None, max_length=2048)
    currency: Literal["EUR", "RUB", "USD"] | None = None
    min_amount_minor: int | None = Field(default=None, ge=1)
    allow_one_time: bool | None = None
    allow_recurring: bool | None = None
    studio_model_id: int | None = Field(default=None, ge=1)
    submit: bool | None = None


class CreatorDonationLinkOut(BaseModel):
    id: int
    studio_model_id: int | None = None
    title: str
    description: str | None = None
    button_text: str | None = None
    cover_image_url: str | None = None
    has_cover: bool = False
    currency: str
    min_amount_minor: int | None = None
    allow_one_time: bool
    allow_recurring: bool
    status: str
    tribute_donation_request_id: int | None = None
    web_link: str | None = None
    telegram_link: str | None = None
    admin_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None = None
    donations_count: int | None = None
    totals_by_currency: dict[str, int] = Field(default_factory=dict)
    pending_payout_by_currency: dict[str, int] = Field(default_factory=dict)


class CreatorDonationEventOut(BaseModel):
    id: int
    creator_donation_link_id: int
    studio_model_id: int | None = None
    event_name: str
    amount_minor: int
    currency: str
    payer_telegram_user_id: int | None = None
    payout_status: str
    occurred_at: datetime


class AdminCreatorDonationLinkOut(CreatorDonationLinkOut):
    user_id: int
    admin_notes_internal: str | None = None


class TributeProductBriefOut(BaseModel):
    id: int
    type: str | None = None
    name: str | None = None
    amount: int | None = None
    currency: str | None = None
    web_link: str | None = None
    telegram_link: str | None = None
    status: str | None = None


class TributeProductsListOut(BaseModel):
    rows: list[TributeProductBriefOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    note: str | None = None


class AdminCreatorDonationActivateIn(BaseModel):
    tribute_donation_request_id: int = Field(ge=1)
    web_link: str = Field(min_length=8, max_length=2048)
    telegram_link: str | None = Field(default=None, max_length=2048)


class AdminCreatorDonationRejectIn(BaseModel):
    admin_notes: str | None = Field(default=None, max_length=2000)


class ChatterStatsRowOut(BaseModel):
    user_id: int
    member_login: str
    is_active: bool
    outbound_messages: int
    conversations_replied: int
    companion_ratings_positive: int
    companion_ratings_negative: int
    median_reply_seconds: int | None = None
    avg_first_response_seconds: int | None = None
    tribute_display_minor: int
    tribute_gross_minor: int
    tribute_currency: str
    tribute_share_percent: int
    tribute_event_count: int


class ChatterStatsSummaryOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_date: date
    to_date: date
    is_owner: bool
    self_row: ChatterStatsRowOut = Field(alias="self")
    members: list[ChatterStatsRowOut] | None = None


class CompanionHealthOut(BaseModel):
    active: bool
    effective_mode: str | None = None
    status: str
    reasons: list[str] = Field(default_factory=list)
    pending_jobs: int = 0
    pending_drafts: int = 0
    relationship_score: int | None = None
    mood: str | None = None
    last_inbound_at: datetime | None = None
    last_sent_at: datetime | None = None


class ChatterSnippetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    lang: str | None = None
    sort_order: int = 0


class ChatterSnippetIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)
    lang: str | None = Field(default=None, max_length=8)
    sort_order: int | None = None


class ChatterSnippetPatchIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    body: str | None = Field(default=None, min_length=1, max_length=4000)
    lang: str | None = Field(default=None, max_length=8)
    sort_order: int | None = None


class IntegrationHealthOut(BaseModel):
    companion_pending_jobs: int = 0
    companion_failed_jobs_24h: int = 0
    companion_style_examples: int = 0
    telegram_webhook_ok: bool = False
    fanvue_oauth_ok: bool = False
    issues: list[str] = Field(default_factory=list)


class FanvueSyncOut(BaseModel):
    chats_processed: int
    messages_imported: int
    messages_skipped: int
    messages_empty: int
    errors: list[str] = Field(default_factory=list)


class IntegrationStatusOut(BaseModel):
    telegram_configured: bool
    telegram_bot_username: str | None = None
    fanvue_configured: bool
    fanvue_creator_uuid: str | None = None
    fanvue_webhook_url: str | None = None
    fanvue_oauth_available: bool = False
    fanvue_oauth_connected: bool = False
    instagram_configured: bool = False
    instagram_oauth_available: bool = False
    instagram_webhook_url: str | None = None
    telegram_webhook_url: str | None = None
    # True, если webhook реально зарегистрирован у Telegram (нужен HTTPS)
    telegram_webhook_registered: bool = False
    integration_hint: str | None = None
    wavespeed_configured: bool = False
    wavespeed_managed_by_platform: bool = False
    llm_configured: bool = False
    telegram_connections: list[PlatformConnectionOut] = Field(default_factory=list)
    fanvue_connections: list[PlatformConnectionOut] = Field(default_factory=list)
    instagram_connections: list[PlatformConnectionOut] = Field(default_factory=list)
    tribute_configured: bool = False
    tribute_connections: list[PlatformConnectionOut] = Field(default_factory=list)
    max_connections_per_platform: int = 1


# --- Billing (YooKassa) ---


class BillingCreditsPricingOut(BaseModel):
    min_quantity: int
    bulk_from: int
    unit_price_rub: float
    bulk_unit_price_rub: float


class BillingPlanItemOut(BaseModel):
    product: str
    title: str
    price_rub: int
    currency: str = "RUB"
    credits_pricing: BillingCreditsPricingOut | None = None


class BillingPlansOut(BaseModel):
    items: list[BillingPlanItemOut]
    catalog: dict[str, Any] | None = None


class ReferralMeOut(BaseModel):
    referral_code: str
    referral_link: str
    invited_count: int
    credits_earned: int
    friend_referral_credits: int
    signup_base_credits: int
    referrer_payment_percent: int
    credit_unit_price_rub: float
    referrer_reward_summary: str


class SubscribeWithCreditsIn(BaseModel):
    product: str = Field(min_length=3, max_length=64)


class SubscribeWithCreditsOut(BaseModel):
    product: str
    credits_spent: int
    price_rub: int
    balance_after: int
    managed_bonus_credits: int


class YookassaPaymentCreateIn(BaseModel):
    product: str = Field(min_length=3, max_length=64)
    credits_quantity: int | None = None

    @model_validator(mode="after")
    def credits_pack_needs_quantity(self) -> YookassaPaymentCreateIn:
        from app.services.plan_catalog import get_plan_spec, resolve_product_id

        p = resolve_product_id(self.product.strip())
        if p == "credits_pack":
            if self.credits_quantity is None:
                raise ValueError("Для покупки кредитов укажите credits_quantity")
        elif self.credits_quantity is not None:
            raise ValueError("Поле credits_quantity только для product=credits_pack")
        elif get_plan_spec(p) is None:
            raise ValueError("Неизвестный продукт подписки")
        return self


class YookassaPaymentOut(BaseModel):
    payment_id: str
    confirmation_url: str


class TributeCheckoutIn(BaseModel):
    product: str = Field(min_length=3, max_length=64)
    credits_quantity: int | None = None

    @model_validator(mode="after")
    def credits_pack_needs_quantity(self) -> TributeCheckoutIn:
        from app.services.tribute_billing_catalog import parse_tribute_billing_catalog
        from app.services.plan_catalog import get_plan_spec, resolve_product_id

        p = resolve_product_id(self.product.strip())
        if p == "credits_pack":
            if self.credits_quantity is None:
                raise ValueError("Для покупки кредитов укажите credits_quantity")
            cat = parse_tribute_billing_catalog(settings.tribute_billing_product_map_json)
            if cat.tribute_product_id_for("credits_pack", credits_quantity=self.credits_quantity) is None:
                raise ValueError("Этот пакет кредитов не настроен для оплаты через Tribute")
        elif self.credits_quantity is not None:
            raise ValueError("Поле credits_quantity только для product=credits_pack")
        elif get_plan_spec(p) is None:
            raise ValueError("Неизвестный продукт подписки")
        return self


class TributeCheckoutOut(BaseModel):
    tribute_product_id: int
    payment_url: str
    telegram_deep_link: str | None = None
    currency: str | None = None
    amount_minor: int | None = None


class PushSubscribeIn(BaseModel):
    endpoint: str
    keys: dict[str, str]

    @field_validator("endpoint")
    @classmethod
    def strip_endpoint(cls, v: object) -> str:
        s = str(v or "").strip()
        if len(s) < 8:
            raise ValueError("invalid endpoint")
        return s

    @field_validator("keys", mode="after")
    @classmethod
    def webpush_keys(cls, v: dict[str, str]) -> dict[str, str]:
        if "p256dh" not in v or "auth" not in v:
            raise ValueError("keys must include p256dh and auth")
        return {k: str(v[k]) for k in v}


class PushUnsubscribeIn(BaseModel):
    endpoint: str

    @field_validator("endpoint")
    @classmethod
    def strip_endpoint(cls, v: object) -> str:
        s = str(v or "").strip()
        if len(s) < 8:
            raise ValueError("invalid endpoint")
        return s


# --- Admin ---


class AdminLabelCount(BaseModel):
    label: str
    count: int


class AdminDayCount(BaseModel):
    date: str
    count: int


class AdminSegmentItemOut(BaseModel):
    user_id: int | None = None
    email: str | None = None
    user_created_at: datetime | None = None
    subscription_status: str | None = None
    billing_plan: str | None = None
    plan_tier: str | None = None
    detail: str | None = None
    occurred_at: datetime | None = None
    payment_id: str | None = None


class AdminSegmentOut(BaseModel):
    segment: str
    title: str
    total: int
    items: list[AdminSegmentItemOut] = []


class AdminEngagementStats(BaseModel):
    """Вовлечённость и конверсия владельцев пространств."""

    active_owners_7d: int = 0
    active_owners_30d: int = 0
    active_owners_7d_pct: float = 0.0
    active_owners_30d_pct: float = 0.0
    paid_active_owners: int = 0
    paid_active_pct: float = 0.0
    trialing_owners: int = 0
    past_due_owners: int = 0
    paid_or_trialing_owners: int = 0
    paid_or_trialing_pct: float = 0.0
    zombie_owners: int = 0
    zombie_pct: float = 0.0
    engaged_owners_ever: int = 0
    owners_yookassa_credits_buyers: int = 0
    owners_with_studio: int = 0
    owners_with_chat: int = 0
    registered_owners_30d: int = 0
    new_paid_active_owners_30d: int = 0
    new_paid_active_30d_pct: float = 0.0


class AdminFunnelStepOut(BaseModel):
    key: str
    label: str
    count: int
    pct_of_registered: float = 0.0


class AdminActivationFunnelOut(BaseModel):
    days: int = 30
    registered: int = 0
    steps: list[AdminFunnelStepOut] = []
    events_by_name: dict[str, int] = {}


class AdminStatsOut(BaseModel):
    total_users: int
    workspace_owners: int
    workspace_members: int
    total_credits_balance: int
    studio_generations_total: int
    usage_by_kind: dict[str, int]
    studio_models_total: int = 0
    studio_model_images_total: int = 0
    studio_images_total: int = 0
    studio_videos_total: int = 0
    studio_motion_renders_total: int = 0
    conversations_total: int = 0
    referrals_total: int = 0
    yookassa_payments_total: int = 0
    subscriptions_by_status: list[AdminLabelCount] = []
    subscriptions_by_plan: list[AdminLabelCount] = []
    registrations_by_day: list[AdminDayCount] = []
    generations_by_day: list[AdminDayCount] = []
    chart_days: int = 30
    engagement: AdminEngagementStats = AdminEngagementStats()
    activation_funnel: AdminActivationFunnelOut = AdminActivationFunnelOut()


class AdminUserRow(BaseModel):
    id: int
    email: str
    created_at: datetime
    is_active: bool
    is_platform_admin: bool
    parent_user_id: int | None = None
    parent_email: str | None = None
    member_login: str | None = None
    subscription_status: str
    """План биллинга: credits | standard | pro."""
    billing_plan: str = "standard"
    plan_tier: str | None = None
    """Дата окончания оплаченного периода подписки владельца (UTC), если задана."""
    subscription_period_end: datetime | None = None
    credits_balance: int
    """Баланс счёта владельца пространства (для участника — тот же, что у владельца)."""
    studio_models_count: int = 0
    """Модели студии владельца пространства."""
    studio_generations_count: int = 0
    """Архив генераций владельца пространства."""


class AdminUserDetailOut(AdminUserRow):
    invited_users_count: int = 0
    referred_by_email: str | None = None
    conversations_count: int = 0
    workspace_members_count: int = 0


class AdminUserPatchIn(BaseModel):
    is_active: bool | None = None
    is_platform_admin: bool | None = None


class AdminCreditsIn(BaseModel):
    delta: int
    note: str | None = Field(default=None, max_length=2000)


class AdminCreditsOut(BaseModel):
    new_balance: int
    billing_user_id: int


class AdminSubscriptionPatchIn(BaseModel):
    status: str | None = Field(
        default=None,
        description="none|incomplete|trialing|active|past_due|canceled|unpaid",
    )
    plan_tier: str | None = Field(
        default=None,
        max_length=64,
        description="solo | pro | studio",
    )
    current_period_end: datetime | None = None
    billing_plan: str | None = Field(
        default=None,
        description="credits | standard | pro (legacy: managed, byok)",
    )

    @field_validator("billing_plan", mode="before")
    @classmethod
    def _norm_billing_plan(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        legacy = {"managed": "standard", "byok": "pro"}
        if s in legacy:
            return legacy[s]
        if s not in ("credits", "standard", "pro"):
            raise ValueError("billing_plan must be credits, standard, or pro")
        return s


class AdminEmailSegmentOption(BaseModel):
    id: str
    title: str


class AdminEmailConfigOut(BaseModel):
    smtp_configured: bool
    from_email: str | None = None
    from_name: str | None = None
    segments: list[AdminEmailSegmentOption] = []


class AdminEmailTemplateOut(BaseModel):
    id: str
    name: str
    subject: str
    body_html: str
    body_text: str = ""


class AdminEmailSegmentPreviewOut(BaseModel):
    segment: str
    title: str
    segment_total: int = 0
    eligible: int = 0
    opted_out: int = 0
    inactive: int = 0


class AdminEmailCampaignOut(BaseModel):
    id: int
    segment: str
    segment_title: str
    subject: str
    body_html: str
    body_text: str | None = None
    status: str
    recipient_count: int = 0
    sent_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AdminEmailCampaignCreateIn(BaseModel):
    segment: str = Field(..., min_length=1, max_length=64)
    subject: str = Field(default="", max_length=500)
    body_html: str = Field(default="")
    body_text: str | None = None
    template_id: str | None = Field(default=None, max_length=64)
    use_template_body: bool = Field(
        default=True,
        description="Подставить HTML/текст из template_id",
    )
    send_now: bool = Field(default=False, description="Сразу поставить в очередь")


class AdminEmailSendTestIn(BaseModel):
    to_email: EmailStr
    subject: str = Field(..., max_length=500)
    body_html: str
    body_text: str | None = None


class AdminExifBotStatsOut(BaseModel):
    total_users: int
    total_profiles: int
    total_processes: int
    processes_today: int
    active_users_7d: int
    active_users_30d: int
    users_with_profiles: int
    utc_day: str


class AdminExifBotUserRow(BaseModel):
    id: int
    telegram_id: int
    username: str | None = None
    display_name: str
    telegram_link: str | None = None
    language_code: str | None = None
    profiles_count: int
    total_process_count: int
    daily_process_count: int
    daily_process_day: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminExifBotProfileRow(BaseModel):
    id: int
    title: str
    camera_preset_id: str | None = None
    has_selfie_ref: bool
    has_main_ref: bool
    has_gps: bool
    is_ready: bool
    created_at: datetime
    updated_at: datetime


class AdminExifBotUserDetailOut(AdminExifBotUserRow):
    profiles: list[AdminExifBotProfileRow] = []


class AdminIgBotStatsOut(BaseModel):
    total_users: int
    total_downloads: int
    downloads_today: int
    active_users_7d: int
    active_users_30d: int
    users_downloaded_today: int
    daily_limit_default: int
    daily_limit_subscribed: int
    utc_day: str


class AdminIgBotUserRow(BaseModel):
    id: int
    telegram_id: int
    username: str | None = None
    display_name: str
    telegram_link: str | None = None
    language_code: str | None = None
    total_process_count: int
    daily_process_count: int
    daily_process_day: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminIgBotUserDetailOut(AdminIgBotUserRow):
    pass
