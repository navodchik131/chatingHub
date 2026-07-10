"""Проверка данных Telegram Login Widget (https://core.telegram.org/widgets/login)."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field


class TelegramLoginPayload(BaseModel):
    id: int = Field(gt=0)
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int = Field(gt=0)
    hash: str = Field(min_length=1)


def _data_check_string(fields: dict[str, Any]) -> str:
    lines = [f"{k}={v}" for k, v in sorted(fields.items()) if v is not None]
    return "\n".join(lines)


def verify_telegram_login_payload(
    payload: TelegramLoginPayload,
    *,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> TelegramLoginPayload:
    token = (bot_token or "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="Telegram Login не настроен на сервере")

    now = int(time.time())
    if payload.auth_date > now + 60:
        raise HTTPException(status_code=400, detail="Некорректная дата авторизации Telegram")
    if max_age_seconds > 0 and now - payload.auth_date > max_age_seconds:
        raise HTTPException(status_code=400, detail="Сессия Telegram устарела — войдите снова")

    raw = payload.model_dump()
    received_hash = str(raw.pop("hash") or "").strip().lower()
    check_fields: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None:
            continue
        check_fields[key] = value

    data_check = _data_check_string(check_fields)
    secret_key = hashlib.sha256(token.encode("utf-8")).digest()
    expected = hmac.new(secret_key, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(status_code=401, detail="Неверная подпись Telegram")

    return payload
