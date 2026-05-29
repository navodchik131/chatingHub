"""Вложения чата: сохранение и JWT."""

from __future__ import annotations

import pytest

from app.services.chat_attachment import (
    create_chat_attachment_access_token,
    decode_chat_attachment_access_token,
    resolve_chat_attachment_file,
    save_chat_image_bytes,
)
from app.services.chat_messages import message_to_out


def test_save_and_resolve_chat_image(tmp_path, monkeypatch):
    from app.config import BACKEND_DIR
    from app.services import chat_attachment as mod

    monkeypatch.setattr(mod, "CHAT_MEDIA_ROOT", tmp_path / "chat_media")
    monkeypatch.setattr(mod, "BACKEND_DIR", tmp_path)

    raw = b"\xff\xd8\xff" + b"x" * 100
    rel, mime = save_chat_image_bytes(owner_id=7, raw=raw, content_type="image/jpeg")
    assert mime == "image/jpeg"
    path = resolve_chat_attachment_file(7, rel)
    assert path is not None and path.read_bytes() == raw


def test_chat_attachment_token_roundtrip():
    tok = create_chat_attachment_access_token(user_id=3, attachment_id=99)
    uid, aid = decode_chat_attachment_access_token(tok)
    assert uid == 3
    assert aid == 99


def test_message_to_out_attachments():
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.db.models import MessageAttachmentKind, MessageDirection

    att = SimpleNamespace(
        id=1,
        kind=MessageAttachmentKind.image,
        mime_type="image/png",
    )
    msg = SimpleNamespace(
        id=10,
        direction=MessageDirection.inbound,
        text_original="hi",
        text_translated="привет",
        created_at=datetime.now(timezone.utc),
        attachments=[att],
    )
    out = message_to_out(msg, owner_id=5)  # type: ignore[arg-type]
    assert len(out.attachments) == 1
    assert out.attachments[0].url.startswith("/api/chat/attachment?t=")
