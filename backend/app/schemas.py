from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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
    is_workspace_owner: bool = True
    workspace_owner_id: int
    member_login: str | None = None
    permissions_mask: int = 0
    owner_email: str


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


class StudioRefinePromptOut(BaseModel):
    refined_prompt: str
    reference_scene_description: str | None = None
    generated_image_url: str | None = None
    wavespeed_message: str | None = None


class WavespeedIntegrationIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=512)

    @field_validator("api_key", mode="before")
    @classmethod
    def strip_key(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()


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
