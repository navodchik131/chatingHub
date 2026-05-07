from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.db.models import MessageDirection, Platform


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    direction: MessageDirection
    text_original: str
    text_translated: str | None
    created_at: datetime


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
    updated_at: datetime
    has_avatar: bool = False


class ConversationWithPreview(ConversationOut):
    last_message_preview: str | None = None
    unread_count: int = 0


class ReplyIn(BaseModel):
    text: str


class ConversationPatchIn(BaseModel):
    """Частичное обновление диалога. Пустая строка в outbound_lang сбрасывает принудительный язык."""

    outbound_lang: str | None = None

    @field_validator("outbound_lang", mode="before")
    @classmethod
    def _strip_outbound_lang(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            return None
        s = v.strip()
        return s if s else None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    """Логин сотрудника внутри пространства (вместе с email владельца)."""
    member_login: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMeOut(BaseModel):
    id: int
    email: str
    subscription_status: str
    credits_balance: int
    """План биллинга владельца пространства: managed | byok."""
    billing_plan: str = "managed"
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


class WorkspaceMemberCreateIn(BaseModel):
    member_login: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    permissions_mask: int | None = None


class WorkspaceMemberPatchIn(BaseModel):
    permissions_mask: int | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None


class WorkspaceMemberOut(BaseModel):
    id: int
    member_login: str
    permissions_mask: int
    is_active: bool


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
    generated_image_url: str | None = None
    wavespeed_message: str | None = None
    generation_id: int | None = None


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
    image_url: str


class StudioGenerationsPageOut(BaseModel):
    items: list[StudioGenerationOut]
    has_more: bool


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


class UserStudioModelOut(BaseModel):
    id: int
    name: str
    profile_text: str
    image_count: int = 0
    images: list[StudioModelImageOut] = Field(default_factory=list)


class UserStudioModelPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    profile_text: str | None = None


class StudioModelProfileGenerateOut(BaseModel):
    """JSON-текст для поля описания модели (внешность / model_profile)."""

    profile_text: str


class TelegramIntegrationIn(BaseModel):
    """Токен BotFather, формат `числа:строка` (обычно ~45+ символов)."""

    bot_token: str = Field(min_length=15, max_length=512)

    @field_validator("bot_token", mode="before")
    @classmethod
    def strip_bot_token(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()


class FanvueIntegrationIn(BaseModel):
    access_token: str = Field(min_length=10)
    creator_uuid: str = Field(min_length=8, max_length=64)
    webhook_signing_secret: str = Field(min_length=4, max_length=512)


class IntegrationStatusOut(BaseModel):
    telegram_configured: bool
    telegram_bot_username: str | None = None
    fanvue_configured: bool
    fanvue_creator_uuid: str | None = None
    fanvue_webhook_url: str | None = None
    telegram_webhook_url: str | None = None
    # True, если webhook реально зарегистрирован у Telegram (нужен HTTPS)
    telegram_webhook_registered: bool = False
    integration_hint: str | None = None
    wavespeed_configured: bool = False
    llm_configured: bool = False


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


class YookassaPaymentCreateIn(BaseModel):
    product: Literal["sub_byok_month", "sub_managed_month", "credits_pack"]
    credits_quantity: int | None = None

    @model_validator(mode="after")
    def credits_pack_needs_quantity(self) -> YookassaPaymentCreateIn:
        if self.product == "credits_pack":
            if self.credits_quantity is None:
                raise ValueError("Для покупки кредитов укажите credits_quantity")
        elif self.credits_quantity is not None:
            raise ValueError("Поле credits_quantity только для product=credits_pack")
        return self


class YookassaPaymentOut(BaseModel):
    payment_id: str
    confirmation_url: str


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


class AdminStatsOut(BaseModel):
    total_users: int
    workspace_owners: int
    workspace_members: int
    total_credits_balance: int
    studio_generations_total: int
    usage_by_kind: dict[str, int]


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
    """План биллинга владельца пространства (managed | byok)."""
    billing_plan: str = "managed"
    """Дата окончания оплаченного периода подписки владельца (UTC), если задана."""
    subscription_period_end: datetime | None = None
    credits_balance: int
    """Баланс счёта владельца пространства (для участника — тот же, что у владельца)."""


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
    plan_tier: str | None = Field(default=None, max_length=64)
    current_period_end: datetime | None = None
    billing_plan: str | None = Field(
        default=None,
        description="managed | byok; биллинг всегда у владельца пространства",
    )

    @field_validator("billing_plan", mode="before")
    @classmethod
    def _norm_billing_plan(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        if s not in ("managed", "byok"):
            raise ValueError("billing_plan must be managed or byok")
        return s
