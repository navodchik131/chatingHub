from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Platform(str, enum.Enum):
    telegram = "telegram"
    fanvue = "fanvue"


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "external_chat_id",
            "external_topic_id",
            name="uq_conv_platform_chat_topic",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), index=True)
    # Для Telegram: id супергруппы direct messages
    external_chat_id: Mapped[str] = mapped_column(String(64), index=True)
    # topic_id из DirectMessagesTopic (строка для единообразия с Fanvue)
    external_topic_id: Mapped[str] = mapped_column(String(64), default="0")
    user_display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_lang: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # id последнего просмотренного сообщения (входящие с id > этого считаются непрочитанными)
    last_read_message_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="conversation", order_by="Message.id"
    )


class MessageDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[MessageDirection] = mapped_column(Enum(MessageDirection))
    text_original: Mapped[str] = mapped_column(Text, default="")
    text_translated: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Сырой payload для отладки (опционально)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="messages"
    )
