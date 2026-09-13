"""Авторизация MTProto: телефон → код → 2FA."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

from app.connectors.telegram_user.client import build_telegram_client
from app.connectors.telegram_user.worker import (
    block_telegram_user_worker_session,
    unblock_telegram_user_worker_session,
)
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


def _normalize_code(code: str) -> str:
    return re.sub(r"\D", "", (code or "").strip())


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

    blocked_session_id: int | None = row.id if row else None
    if blocked_session_id is not None:
        # Worker держит тот же auth key — параллельный connect даёт «disconnected».
        await block_telegram_user_worker_session(blocked_session_id)

    # Новая StringSession на каждый send_code: hash привязан к auth key этой сессии.
    client = build_telegram_client(session_encrypted=None)
    pending_session_enc: str | None = None
    try:
        await client.connect()
        if not client.is_connected():
            raise RuntimeError("Не удалось подключиться к Telegram — проверьте сеть или TELEGRAM_PROXY.")
        sent = await client.send_code_request(normalized)
        phone_code_hash = sent.phone_code_hash
        pending_session_enc = encrypt_secret(client.session.save())
    finally:
        try:
            await client.disconnect()
        except Exception:
            log.exception("telegram_user login disconnect failed phone=%s", normalized[-4:])
        if blocked_session_id is not None:
            unblock_telegram_user_worker_session(blocked_session_id)

    enc_hash = encrypt_secret(phone_code_hash)
    if row is None:
        row = TelegramUserSession(
            user_id=owner_id,
            label=(label or "").strip() or None,
            studio_model_id=studio_model_id,
            phone=normalized,
            phone_code_hash_encrypted=enc_hash,
            session_encrypted=pending_session_enc,
            status=TelegramUserSessionStatus.pending_otp.value,
            is_active=True,
            error_message=None,
        )
        session.add(row)
    else:
        row.phone = normalized
        row.phone_code_hash_encrypted = enc_hash
        row.session_encrypted = pending_session_enc
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
    if not row.session_encrypted:
        raise ValueError("Сессия авторизации утеряна — запросите код заново.")

    phone = row.phone
    phone_code_hash = decrypt_secret(row.phone_code_hash_encrypted)
    otp = _normalize_code(code)
    if not otp:
        raise ValueError("Введите код из Telegram или SMS.")

    await block_telegram_user_worker_session(row.id)
    client = build_telegram_client(session_encrypted=row.session_encrypted)
    try:
        await client.connect()
        if not client.is_connected():
            raise RuntimeError("Не удалось подключиться к Telegram — запросите код заново.")
        try:
            await client.sign_in(phone, otp, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            row.session_encrypted = encrypt_secret(client.session.save())
            row.status = TelegramUserSessionStatus.pending_2fa.value
            row.phone_code_hash_encrypted = None
            row.updated_at = datetime.now(timezone.utc)
            await session.flush()
            return row, True
        except PhoneCodeExpiredError as e:
            log.warning("telegram_user login code expired phone=%s", phone[-4:])
            raise ValueError(
                "Код истёк. Нажмите «Отправить код» ещё раз и введите новый код."
            ) from e
        except PhoneCodeInvalidError as e:
            log.warning("telegram_user login invalid code phone=%s", phone[-4:])
            raise ValueError(
                "Неверный код. Проверьте цифры из Telegram (не SMS, если код пришёл в приложение)."
            ) from e

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
        try:
            await client.disconnect()
        except Exception:
            log.exception("telegram_user confirm code disconnect failed session=%s", row.id)
        unblock_telegram_user_worker_session(row.id)


async def confirm_telegram_user_password(
    session: AsyncSession,
    *,
    row: TelegramUserSession,
    password: str,
) -> TelegramUserSession:
    if row.status != TelegramUserSessionStatus.pending_2fa.value:
        raise ValueError("2FA not required")
    await block_telegram_user_worker_session(row.id)
    client = build_telegram_client(session_encrypted=row.session_encrypted)
    try:
        await client.connect()
        if not client.is_connected():
            raise RuntimeError("Не удалось подключиться к Telegram — повторите ввод пароля.")
        try:
            await client.sign_in(password=(password or "").strip())
        except PasswordHashInvalidError as e:
            raise ValueError(
                "Неверный облачный пароль 2FA. Проверьте пароль в настройках Telegram → Конфиденциальность."
            ) from e
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
        try:
            await client.disconnect()
        except Exception:
            log.exception("telegram_user confirm password disconnect failed session=%s", row.id)
        unblock_telegram_user_worker_session(row.id)
