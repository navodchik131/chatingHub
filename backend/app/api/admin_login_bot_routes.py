"""API рассылок login Telegram-бота в админке."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_platform_admin
from app.config import settings
from app.db.models import User
from app.db.session import get_session
from app.schemas import (
    AdminLoginBotBroadcastIn,
    AdminLoginBotBroadcastOut,
    AdminLoginBotConfigOut,
    AdminLoginBotSendTestIn,
    AdminLoginBotStatsOut,
    AdminLoginBotTemplateOut,
)
from app.services.telegram_login_bot_broadcast import (
    broadcast_login_bot_message,
    send_login_bot_message,
)
from app.services.telegram_login_bot_contacts import build_login_bot_admin_stats
from app.services.telegram_login_bot_templates import (
    list_login_bot_templates,
    render_login_bot_template,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["admin-login-bot"])


def _empty_stats() -> dict[str, int]:
    return {
        "total_contacts": 0,
        "reachable_contacts": 0,
        "blocked_contacts": 0,
        "active_contacts_7d": 0,
        "active_contacts_30d": 0,
    }


async def _load_stats(session: AsyncSession) -> dict[str, int]:
    try:
        stats = await build_login_bot_admin_stats(session)
        await session.commit()
        return stats
    except Exception:
        log.exception("login bot admin stats failed")
        await session.rollback()
        return _empty_stats()


def _require_login_bot() -> None:
    if not settings.telegram_login_configured:
        raise HTTPException(
            status_code=503,
            detail="Login-бот не настроен. Укажите TELEGRAM_LOGIN_BOT_TOKEN и TELEGRAM_LOGIN_BOT_USERNAME",
        )


@router.get("/admin/login-bot/config", response_model=AdminLoginBotConfigOut)
async def admin_login_bot_config(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminLoginBotConfigOut:
    stats = await _load_stats(session)
    username = (settings.telegram_login_bot_username or "").strip().lstrip("@")
    return AdminLoginBotConfigOut(
        bot_configured=settings.telegram_login_configured,
        bot_username=username or None,
        channel_url=(settings.telegram_login_news_channel_url or "").strip() or None,
        channel_label=(settings.telegram_login_news_channel_label or "").strip() or None,
        bot_url=f"https://t.me/{username}" if username else None,
        recipient_count=stats["reachable_contacts"],
        templates=[AdminLoginBotTemplateOut(**t) for t in list_login_bot_templates()],
    )


@router.get("/admin/login-bot/stats", response_model=AdminLoginBotStatsOut)
async def admin_login_bot_stats(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminLoginBotStatsOut:
    stats = await _load_stats(session)
    return AdminLoginBotStatsOut(**stats)


@router.post("/admin/login-bot/test")
async def admin_login_bot_send_test(
    body: AdminLoginBotSendTestIn,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_platform_admin),
) -> dict:
    _require_login_bot()
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст сообщения обязателен")

    telegram_id = body.telegram_id
    if telegram_id is None:
        if admin.telegram_id is None:
            raise HTTPException(
                status_code=400,
                detail="Укажите telegram_id или привяжите Telegram к аккаунту администратора",
            )
        telegram_id = int(admin.telegram_id)

    try:
        await send_login_bot_message(
            session,
            telegram_id=telegram_id,
            text=text,
            parse_mode=body.parse_mode,
            disable_web_page_preview=body.disable_web_page_preview,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"ok": True, "telegram_id": telegram_id}


@router.post("/admin/login-bot/broadcast", response_model=AdminLoginBotBroadcastOut)
async def admin_login_bot_broadcast(
    body: AdminLoginBotBroadcastIn,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminLoginBotBroadcastOut:
    _require_login_bot()

    text = (body.text or "").strip()
    if body.template_id:
        rendered = render_login_bot_template(body.template_id.strip())
        if not rendered:
            raise HTTPException(status_code=400, detail="Неизвестный шаблон")
        if body.use_template_body or not text:
            text = rendered

    if not text:
        raise HTTPException(status_code=400, detail="Текст сообщения обязателен")

    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Подтвердите рассылку (confirm: true)",
        )

    try:
        result = await broadcast_login_bot_message(
            session,
            text=text,
            parse_mode=body.parse_mode,
            disable_web_page_preview=body.disable_web_page_preview,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return AdminLoginBotBroadcastOut(
        total=result.total,
        sent=result.sent,
        failed=result.failed,
        blocked=result.blocked,
        errors=result.errors,
    )
