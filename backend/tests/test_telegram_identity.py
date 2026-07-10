"""Тесты Telegram Login Widget и identity."""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest
from fastapi import HTTPException

from app.auth.telegram_login import TelegramLoginPayload, verify_telegram_login_payload
from app.services.telegram_identity import (
    is_real_owner_email,
    owner_email_setup_required,
    parse_synthetic_telegram_id,
    synthetic_telegram_email,
)


def _sign_payload(fields: dict, bot_token: str) -> str:
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    return hmac.new(secret, check.encode("utf-8"), hashlib.sha256).hexdigest()


def test_verify_telegram_login_payload_ok():
    token = "123456:ABC-DEF"
    fields = {
        "id": 424242,
        "first_name": "Ann",
        "username": "ann_test",
        "auth_date": int(time.time()),
    }
    payload = TelegramLoginPayload(
        **fields,
        hash=_sign_payload(fields, token),
    )
    out = verify_telegram_login_payload(payload, bot_token=token, max_age_seconds=3600)
    assert out.id == 424242


def test_verify_telegram_login_payload_bad_hash():
    token = "123456:ABC-DEF"
    fields = {"id": 1, "auth_date": int(time.time())}
    payload = TelegramLoginPayload(**fields, hash="deadbeef")
    with pytest.raises(HTTPException) as exc:
        verify_telegram_login_payload(payload, bot_token=token)
    assert exc.value.status_code == 401


def test_synthetic_telegram_email_roundtrip():
    email = synthetic_telegram_email(999001)
    assert email == "tg999001@telegram.local"
    assert parse_synthetic_telegram_id(email) == 999001
    assert not is_real_owner_email(email)
    assert is_real_owner_email("owner@example.com")


class _UserStub:
    def __init__(self, *, email: str, parent_user_id=None, auth_email_verified=True, telegram_id=None):
        self.email = email
        self.parent_user_id = parent_user_id
        self.auth_email_verified = auth_email_verified
        self.telegram_id = telegram_id


def test_owner_email_setup_required_for_tg_only():
    u = _UserStub(email=synthetic_telegram_email(1), auth_email_verified=False)
    assert owner_email_setup_required(u)


def test_owner_email_setup_not_required_when_verified():
    u = _UserStub(email="real@example.com", auth_email_verified=True)
    assert not owner_email_setup_required(u)
