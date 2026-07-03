"""Настройки companion bot: подключение + переопределение на диалог."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CompanionBotMode,
    Conversation,
    FanvueConnection,
    Platform,
    TelegramConnection,
)
from app.services.platform_connections import (
    resolve_fanvue_connection_for_conversation,
    resolve_telegram_connection_for_conversation,
)


@dataclass(frozen=True)
class CompanionConnectionConfig:
    mode: CompanionBotMode
    delay_min_sec: int
    delay_max_sec: int
    max_replies_per_hour: int
    studio_model_id: int | None
    connection_id: int
    platform: Platform
    effective_from: str  # "connection" | "conversation"


def _parse_mode(raw: str | None) -> CompanionBotMode:
    val = (raw or CompanionBotMode.off.value).strip().lower()
    try:
        return CompanionBotMode(val)
    except ValueError:
        return CompanionBotMode.off


def _resolve_effective_mode(
    conv: Conversation,
    conn: TelegramConnection | FanvueConnection,
) -> CompanionBotMode:
    override = (conv.companion_mode_override or "").strip().lower()
    if override:
        return _parse_mode(override)
    return _parse_mode(conn.companion_mode)


def _config_from_connection(
    conn: TelegramConnection | FanvueConnection,
    *,
    platform: Platform,
    mode: CompanionBotMode,
    effective_from: str,
) -> CompanionConnectionConfig:
    delay_min = max(0, int(conn.companion_delay_min_sec or 5))
    delay_max = max(delay_min, int(conn.companion_delay_max_sec or 45))
    return CompanionConnectionConfig(
        mode=mode,
        delay_min_sec=delay_min,
        delay_max_sec=delay_max,
        max_replies_per_hour=max(1, int(conn.companion_max_replies_per_hour or 60)),
        studio_model_id=conn.studio_model_id,
        connection_id=conn.id,
        platform=platform,
        effective_from=effective_from,
    )


async def get_companion_config_for_conversation(
    session: AsyncSession,
    conv: Conversation,
    *,
    owner_id: int | None = None,
) -> CompanionConnectionConfig | None:
    oid = owner_id if owner_id is not None else conv.user_id
    conn: TelegramConnection | FanvueConnection | None = None
    platform: Platform | None = None

    if conv.platform == Platform.telegram:
        conn = await resolve_telegram_connection_for_conversation(session, conv, oid)
        platform = Platform.telegram
        if conn and not conn.is_active:
            conn = None
    elif conv.platform == Platform.fanvue:
        conn = await resolve_fanvue_connection_for_conversation(session, conv, oid)
        platform = Platform.fanvue

    if not conn or platform is None:
        return None

    mode = _resolve_effective_mode(conv, conn)
    if mode == CompanionBotMode.off:
        return None

    src = (
        "conversation"
        if (conv.companion_mode_override or "").strip()
        else "connection"
    )
    return _config_from_connection(conn, platform=platform, mode=mode, effective_from=src)


async def companion_bot_active_for_conversation(
    session: AsyncSession,
    conv: Conversation,
    *,
    owner_id: int | None = None,
) -> bool:
    return await get_companion_config_for_conversation(
        session, conv, owner_id=owner_id
    ) is not None


async def effective_companion_bot_mode(
    session: AsyncSession,
    conv: Conversation,
    *,
    owner_id: int | None = None,
) -> CompanionBotMode | None:
    cfg = await get_companion_config_for_conversation(session, conv, owner_id=owner_id)
    return cfg.mode if cfg else None
