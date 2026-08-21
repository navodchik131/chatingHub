"""API подключения личного Telegram (@username) через MTProto."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.connectors.telegram_user.login import (
    confirm_telegram_user_code,
    confirm_telegram_user_password,
    start_telegram_user_login,
)
from app.connectors.telegram_user.worker import request_telegram_user_worker_refresh
from app.db.models import Platform, Subscription, TelegramUserSession, TelegramUserSessionStatus, User
from app.db.session import get_session
from app.schemas import (
    IntegrationStatusOut,
    PlatformConnectionOut,
    PlatformConnectionPatchIn,
    TelegramUserLoginCodeIn,
    TelegramUserLoginOut,
    TelegramUserLoginPasswordIn,
    TelegramUserLoginStartIn,
)
from app.services.platform_connections import (
    assert_can_add_platform_connection,
    sync_conversations_model_from_connection,
    validate_connection_studio_model,
)
from app.services.workspace import PERM_INTEGRATIONS, assert_permission, workspace_owner_id

log = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/telegram-user", tags=["integrations"])


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 4:
        return phone
    return f"***{digits[-4:]}"


def _telegram_user_connection_out(row: TelegramUserSession) -> PlatformConnectionOut:
    username = (row.telegram_username or "").strip()
    return PlatformConnectionOut(
        id=row.id,
        platform="telegram_user",
        label=row.label,
        studio_model_id=row.studio_model_id,
        telegram_username=username or None,
        bot_username=f"@{username}" if username else None,
        session_status=row.status,
        phone_masked=_mask_phone(row.phone),
        last_seen_at=row.last_seen_at,
        is_active=bool(row.is_active and row.status == TelegramUserSessionStatus.active.value),
        companion_mode=row.companion_mode or "off",
        companion_delay_min_sec=int(row.companion_delay_min_sec or 5),
        companion_delay_max_sec=int(row.companion_delay_max_sec or 45),
        companion_max_replies_per_hour=int(row.companion_max_replies_per_hour or 60),
    )


def _login_out(row: TelegramUserSession, *, needs_password: bool = False) -> TelegramUserLoginOut:
    username = (row.telegram_username or "").strip()
    return TelegramUserLoginOut(
        connection_id=row.id,
        status=row.status,
        needs_password=needs_password,
        telegram_username=f"@{username}" if username else None,
        phone_masked=_mask_phone(row.phone),
    )


async def _integration_status_from_session(
    session: AsyncSession, user: User
) -> IntegrationStatusOut:
    from app.api.integrations_routes import _integration_status

    return await _integration_status(session, user)


@router.post("/start", response_model=TelegramUserLoginOut)
async def telegram_user_login_start(
    body: TelegramUserLoginStartIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TelegramUserLoginOut:
    assert_permission(user, PERM_INTEGRATIONS)
    if not settings.telegram_mtproto_configured:
        raise HTTPException(
            status_code=503,
            detail="MTProto не настроен на сервере (TELEGRAM_API_ID / TELEGRAM_API_HASH).",
        )
    oid = workspace_owner_id(user)
    sub = await session.scalar(select(Subscription).where(Subscription.user_id == oid))
    if body.studio_model_id is not None:
        await validate_connection_studio_model(session, oid, body.studio_model_id)

    is_new = body.connection_id is None
    if is_new:
        await assert_can_add_platform_connection(
            session, oid, sub, platform=Platform.telegram_user
        )

    try:
        row = await start_telegram_user_login(
            session,
            owner_id=oid,
            phone=body.phone,
            label=body.label,
            studio_model_id=body.studio_model_id,
            connection_id=body.connection_id,
        )
        await session.commit()
        await session.refresh(row)
        return _login_out(row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        log.exception("telegram_user login start failed owner=%s", oid)
        raise HTTPException(status_code=400, detail=f"Не удалось отправить код: {e}") from e


@router.post("/confirm-code", response_model=TelegramUserLoginOut)
async def telegram_user_confirm_code(
    body: TelegramUserLoginCodeIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TelegramUserLoginOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    row = await session.scalar(
        select(TelegramUserSession).where(
            TelegramUserSession.id == body.connection_id,
            TelegramUserSession.user_id == oid,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Подключение не найдено")
    try:
        row, needs_password = await confirm_telegram_user_code(
            session, row=row, code=body.code
        )
        await session.commit()
        await session.refresh(row)
        if not needs_password:
            request_telegram_user_worker_refresh()
        return _login_out(row, needs_password=needs_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        log.exception("telegram_user confirm code failed owner=%s", oid)
        raise HTTPException(status_code=400, detail=f"Не удалось подтвердить код: {e}") from e


@router.post("/confirm-password", response_model=TelegramUserLoginOut)
async def telegram_user_confirm_password(
    body: TelegramUserLoginPasswordIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TelegramUserLoginOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    row = await session.scalar(
        select(TelegramUserSession).where(
            TelegramUserSession.id == body.connection_id,
            TelegramUserSession.user_id == oid,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Подключение не найдено")
    try:
        row = await confirm_telegram_user_password(session, row=row, password=body.password)
        await session.commit()
        await session.refresh(row)
        request_telegram_user_worker_refresh()
        return _login_out(row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        log.exception("telegram_user confirm password failed owner=%s", oid)
        raise HTTPException(status_code=400, detail=f"Не удалось подтвердить пароль: {e}") from e


@router.patch("/{connection_id}", response_model=IntegrationStatusOut)
async def patch_telegram_user_connection(
    connection_id: int,
    body: PlatformConnectionPatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    from app.api.integrations_routes import (
        _apply_companion_connection_patch,
        _assert_companion_plan_if_enabling,
    )

    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    row = await session.scalar(
        select(TelegramUserSession).where(
            TelegramUserSession.id == connection_id,
            TelegramUserSession.user_id == oid,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Подключение не найдено")
    if "label" in body.model_fields_set:
        row.label = (body.label or "").strip() or None
    if "studio_model_id" in body.model_fields_set:
        await validate_connection_studio_model(session, oid, body.studio_model_id)
        row.studio_model_id = body.studio_model_id
        await sync_conversations_model_from_connection(
            session,
            platform=Platform.telegram_user,
            connection_id=row.id,
            studio_model_id=body.studio_model_id,
        )
    await _assert_companion_plan_if_enabling(session, oid, body)
    _apply_companion_connection_patch(row, body)
    await session.commit()
    request_telegram_user_worker_refresh()
    return await _integration_status_from_session(session, user)


@router.delete("/{connection_id}", response_model=IntegrationStatusOut)
async def delete_telegram_user_connection(
    connection_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    row = await session.scalar(
        select(TelegramUserSession).where(
            TelegramUserSession.id == connection_id,
            TelegramUserSession.user_id == oid,
        )
    )
    if row:
        row.is_active = False
        row.status = TelegramUserSessionStatus.disconnected.value
        await session.commit()
        request_telegram_user_worker_refresh()
    return await _integration_status_from_session(session, user)
