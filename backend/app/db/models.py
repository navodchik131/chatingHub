from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Platform(str, enum.Enum):
    telegram = "telegram"
    fanvue = "fanvue"


class MessageDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class SubscriptionStatus(str, enum.Enum):
    none = "none"
    incomplete = "incomplete"
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    unpaid = "unpaid"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # вместе с ADMIN_EMAILS в .env — доступ к /api/admin
    """Владелец рабочего пространства; у основного аккаунта NULL."""
    parent_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    """Короткий логин сотрудника внутри пространства (уникален вместе с parent_user_id)."""
    member_login: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """Битовая маска прав (см. app.services.workspace); у владельца не используется."""
    permissions_mask: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    parent: Mapped[User | None] = relationship(
        "User",
        remote_side=[id],
        back_populates="workspace_members",
        foreign_keys=[parent_user_id],
    )
    workspace_members: Mapped[list[User]] = relationship(
        "User",
        back_populates="parent",
        foreign_keys=[parent_user_id],
    )

    subscription: Mapped[Subscription | None] = relationship(
        "Subscription", back_populates="user", uselist=False
    )
    credit_account: Mapped[CreditAccount | None] = relationship(
        "CreditAccount", back_populates="user", uselist=False
    )
    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="owner"
    )
    telegram_connection: Mapped[TelegramConnection | None] = relationship(
        "TelegramConnection", back_populates="user", uselist=False
    )
    fanvue_connection: Mapped[FanvueConnection | None] = relationship(
        "FanvueConnection", back_populates="user", uselist=False
    )
    studio_models: Mapped[list[UserStudioModel]] = relationship(
        "UserStudioModel", back_populates="owner", cascade="all, delete-orphan"
    )
    studio_generations: Mapped[list["StudioGeneration"]] = relationship(
        "StudioGeneration",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    studio_motion_renders: Mapped[list["StudioMotionRender"]] = relationship(
        "StudioMotionRender",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    wavespeed_connection: Mapped[WavespeedConnection | None] = relationship(
        "WavespeedConnection", back_populates="user", uselist=False
    )
    llm_connection: Mapped["LlmConnection | None"] = relationship(
        "LlmConnection", back_populates="user", uselist=False
    )
    push_subscriptions: Mapped[list["PushSubscription"]] = relationship(
        "PushSubscription",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    # managed: кредиты на студию; WaveSpeed — платформенный после оплаты или свой в trial/BYOK; LLM студии — с сервера
    billing_plan: Mapped[str] = mapped_column(
        String(16), default="managed", nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, native_enum=False, length=32),
        default=SubscriptionStatus.none,
    )
    plan_tier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped[User] = relationship("User", back_populates="subscription")


class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    balance: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped[User] = relationship("User", back_populates="credit_account")


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(64), index=True)
    credits_delta: Mapped[int] = mapped_column(Integer)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class YookassaProcessedPayment(Base):
    """Идемпотентность вебхуков: один payment_id — одна выдача."""

    __tablename__ = "yookassa_processed_payments"

    payment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TelegramConnection(Base):
    __tablename__ = "telegram_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    bot_token_encrypted: Mapped[str] = mapped_column(Text)
    webhook_secret: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    bot_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Установлено в True после успешного setWebhook (только HTTPS)
    webhook_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship("User", back_populates="telegram_connection")


class FanvueConnection(Base):
    __tablename__ = "fanvue_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    creator_uuid: Mapped[str] = mapped_column(String(64), index=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    webhook_signing_secret_encrypted: Mapped[str] = mapped_column(Text)
    webhook_secret: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship("User", back_populates="fanvue_connection")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "platform",
            "external_chat_id",
            "external_topic_id",
            name="uq_conv_user_platform_chat_topic",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, native_enum=False, length=16), index=True
    )
    external_chat_id: Mapped[str] = mapped_column(String(64), index=True)
    external_topic_id: Mapped[str] = mapped_column(String(64), default="0")
    user_display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_lang: Mapped[str | None] = mapped_column(String(16), nullable=True)
    """Принудительный целевой язык исходящих (код ISO). NULL = взять из user_lang (последние входящие)."""
    outbound_lang: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # file_id варианта фото профиля (Telegram), только для platform=telegram
    telegram_photo_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Модель студии для доступа операторов; NULL — диалог виден только владельцу."""
    studio_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_studio_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_read_message_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner: Mapped[User] = relationship("User", back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="conversation", order_by="Message.id"
    )

    @property
    def has_avatar(self) -> bool:
        return bool(self.telegram_photo_file_id)


class WavespeedConnection(Base):
    __tablename__ = "wavespeed_connections"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship("User", back_populates="wavespeed_connection")


class LlmConnection(Base):
    """OpenAI-совместимый API (OpenAI, Grok/xAI и др.) для студии при тарифе BYOK."""

    __tablename__ = "llm_connections"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship("User", back_populates="llm_connection")


class PushSubscription(Base):
    """Подписка Web Push (браузер) для владельца пространства (тот же user_id, что и WS hub)."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True, index=True)
    p256dh: Mapped[str] = mapped_column(String(256))
    auth: Mapped[str] = mapped_column(String(256))
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship("User", back_populates="push_subscriptions")


class WorkspaceMemberStudioModel(Base):
    """Ручной allowlist: какие модели студии доступны участнику workspace."""

    __tablename__ = "workspace_member_studio_models"
    __table_args__ = (
        UniqueConstraint(
            "member_user_id",
            "studio_model_id",
            name="uq_wmsm_member_model",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    member_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    studio_model_id: Mapped[int] = mapped_column(
        ForeignKey("user_studio_models.id", ondelete="CASCADE"), index=True
    )


class UserStudioModel(Base):
    """Сохранённый профиль модели для студии (внешность + референс-фото на диске)."""

    __tablename__ = "user_studio_models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    profile_text: Mapped[str] = mapped_column(Text, default="")
    """Пресет «экспорт как с телефона» — id из /api/studio/camera-presets; пусто = без постобработки."""
    camera_preset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    export_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    export_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    owner: Mapped[User] = relationship("User", back_populates="studio_models")
    images: Mapped[list[UserStudioModelImage]] = relationship(
        "UserStudioModelImage",
        back_populates="studio_model",
        cascade="all, delete-orphan",
        order_by="UserStudioModelImage.id",
    )


class UserStudioModelImage(Base):
    __tablename__ = "user_studio_model_images"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    studio_model_id: Mapped[int] = mapped_column(
        ForeignKey("user_studio_models.id", ondelete="CASCADE"), index=True
    )
    relative_path: Mapped[str] = mapped_column(String(512))
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """face | body | genitals | other — роль снимка для image-edit и LLM (порядок в API)."""
    image_kind: Mapped[str] = mapped_column(String(24), default="other", nullable=False)
    """Подставлять ли в EXIF метаданные передней (селфи) камеры для этого кадра (участвует в выборе при экспорте)."""
    export_selfie: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    studio_model: Mapped[UserStudioModel] = relationship(
        "UserStudioModel", back_populates="images"
    )


class StudioGeneration(Base):
    """Архив результатов студии (картинка на диске; URL WaveSpeed может протухнуть)."""

    __tablename__ = "studio_generations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="ready", index=True)
    relative_path: Mapped[str] = mapped_column(String(512), default="")
    content_type: Mapped[str] = mapped_column(String(64), default="image/png")
    output_aspect: Mapped[str | None] = mapped_column(String(32), nullable=True)
    studio_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_studio_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    studio_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("studio_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prompt_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    refined_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Краткое описание референс-видео (vision) для шага Seedance video-edit после перезагрузки клиента
    motion_video_prompt_auto: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    wavespeed_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_step: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    owner: Mapped[User] = relationship("User", back_populates="studio_generations")
    motion_renders: Mapped[list["StudioMotionRender"]] = relationship(
        "StudioMotionRender", back_populates="studio_generation"
    )


class StudioJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class StudioJob(Base):
    """Фоновая задача студии (генерация, motion, апскейл) — HTTP 202 + poll / WebSocket."""

    __tablename__ = "studio_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default=StudioJobStatus.pending.value, index=True)
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship("User", foreign_keys=[user_id])
    actor: Mapped[User] = relationship("User", foreign_keys=[actor_user_id])


class StudioMotionRender(Base):
    """История финальных видео по шагу «Сделать видео» (URL у провайдера; для списка в кабинете)."""

    __tablename__ = "studio_motion_renders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    studio_generation_id: Mapped[int | None] = mapped_column(
        ForeignKey("studio_generations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    studio_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_studio_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    owner: Mapped[User] = relationship("User", back_populates="studio_motion_renders")
    studio_generation: Mapped["StudioGeneration"] = relationship(
        "StudioGeneration", back_populates="motion_renders"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, native_enum=False, length=16)
    )
    text_original: Mapped[str] = mapped_column(Text, default="")
    text_translated: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="messages"
    )
