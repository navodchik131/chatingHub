from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
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
    wavespeed_connection: Mapped[WavespeedConnection | None] = relationship(
        "WavespeedConnection", back_populates="user", uselist=False
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
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
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
    # file_id варианта фото профиля (Telegram), только для platform=telegram
    telegram_photo_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
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


class UserStudioModel(Base):
    """Сохранённый профиль модели для студии (внешность + референс-фото на диске)."""

    __tablename__ = "user_studio_models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    profile_text: Mapped[str] = mapped_column(Text, default="")
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    studio_model: Mapped[UserStudioModel] = relationship(
        "UserStudioModel", back_populates="images"
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
