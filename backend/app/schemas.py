from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
    updated_at: datetime


class ConversationWithPreview(ConversationOut):
    last_message_preview: str | None = None
    unread_count: int = 0


class ReplyIn(BaseModel):
    text: str
