"""Авторизация MTProto: телефон → код → 2FA."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

from app.connectors.telegram_user.client import build_telegram_client
from app.db.models import TelegramUserSession, TelegramUserSessionStatus
from app.services.crypto_secret import decrypt_secret, encrypt_secret

log = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> str:
    raw = (phone or "").strip().replace(" ", "").replace("-", "")
    if not raw:
        raise ValueError("empty phone")
    if raw.startswith("8") and len(raw) == 11:
        raw = "+7" + raw[1:]
    if raw.isdigit() and not raw.startswith("+"):
        raw = "+" + raw
    return raw


async def start_telegram_user_login(
    session: AsyncSession,
    *,
    owner_id: int,
    phone: str,
    label: str | None,
    studio_model_id: int | None,
    connection_id: int | None,
) -> TelegramUserSession:
    normalized = _normalize_phone(phone)
    row: TelegramUserSession | None = None
    if connection_id is not None:
        row = await session.get(TelegramUserSession, connection_id)
        if not row or row.user_id != owner_id:
            raise ValueError("session not found")

    client = build_telegram_client()
    try:
        await client.connect()
        sent = await client.send_code_request(normalized)
        phone_code_hash = sent.phone_code_hash
    finally:
        await client.disconnect()

    enc_hash = encrypt_secret(phone_code_hash)
    if row is None:
        row = TelegramUserSession(
            user_id=owner_id,
            label=(label or "").strip() or None,
            studio_model_id=studio_model_id,
            phone=normalized,
            phone_code_hash_encrypted=enc_hash,
            status=TelegramUserSessionStatus.pending_otp.value,
            is_active=True,
            error_message=None,
        )
        session.add(row)
    else:
        row.phone = normalized
        row.phone_code_hash_encrypted = enc_hash
        row.session_encrypted = None
        row.telegram_user_id = None
        row.telegram_username = None
        row.status = TelegramUserSessionStatus.pending_otp.value
        row.error_message = None
        row.is_active = True
        if label is not None:
            row.label = (label or "").strip() or None
        if studio_model_id is not None:
            row.studio_model_id = studio_model_id
    row.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return row


async def confirm_telegram_user_code(
    session: AsyncSession,
    *,
    row: TelegramUserSession,
    code: str,
) -> tuple[TelegramUserSession, bool]:
    """Подтверждение SMS-кода. Возвращает (row, needs_password)."""
    if row.status not in (
        TelegramUserSessionStatus.pending_otp.value,
        TelegramUserSessionStatus.pending_2fa.value,
    ):
        raise ValueError("invalid session status")
    if not row.phone or not row.phone_code_hash_encrypted:
        raise ValueError("login not started")

    phone = row.phone
    phone_code_hash = decrypt_secret(row.phone_code_hash_encrypted)
    client = build_telegram_client(session_encrypted=row.session_encrypted)
    try:
        await client.connect()
        try:
            await client.sign_in(phone, (code or "").strip(), phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            row.session_encrypted = encrypt_secret(client.session.save())
            row.status = TelegramUserSessionStatus.pending_2fa.value
            row.phone_code_hash_encrypted = None
            row.updated_at = datetime.now(timezone.utc)
            await session.flush()
            return row, True
        except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
            row.status = TelegramUserSessionStatus.error.value
            row.error_message = str(e)[:500]
            row.updated_at = datetime.now(timezone.utc)
            await session.flush()
            raise ValueError("invalid or expired code") from e

        me = await client.get_me()
        row.session_encrypted = encrypt_secret(client.session.save())
        row.telegram_user_id = int(me.id) if me else None
        row.telegram_username = (me.username or "").strip() or None if me else None
        row.phone_code_hash_encrypted = None
        row.status = TelegramUserSessionStatus.active.value
        row.error_message = None
        row.last_seen_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return row, False
    except PhoneNumberInvalidError as e:
        row.status = TelegramUserSessionStatus.error.value
        row.error_message = str(e)[:500]
        await session.flush()
        raise ValueError("invalid phone") from e
    finally:
        await client.disconnect()


async def confirm_telegram_user_password(
    session: AsyncSession,
    *,
    row: TelegramUserSession,
    password: str,
) -> TelegramUserSession:
    if row.status != TelegramUserSessionStatus.pending_2fa.value:
        raise ValueError("2FA not required")
    client = build_telegram_client(session_encrypted=row.session_encrypted)
    try:
        await client.connect()
        await client.sign_in(password=(password or "").strip())
        me = await client.get_me()
        row.session_encrypted = encrypt_secret(client.session.save())
        row.telegram_user_id = int(me.id) if me else None
        row.telegram_username = (me.username or "").strip() or None if me else None
        row.phone_code_hash_encrypted = None
        row.status = TelegramUserSessionStatus.active.value
        row.error_message = None
        row.last_seen_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return row
    finally:
        await client.disconnect()
