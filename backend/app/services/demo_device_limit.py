"""Лимит бесплатных демо-генераций на устройство (IP + UA + client id)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import DemoDeviceQuota
from app.services.device_signal import DeviceSignal


def demo_device_limit() -> int:
    return max(0, int(settings.demo_device_limit))


async def get_or_create_device_quota(
    session: AsyncSession,
    signal: DeviceSignal,
) -> DemoDeviceQuota:
    row = await session.scalar(
        select(DemoDeviceQuota).where(DemoDeviceQuota.device_key == signal.device_key)
    )
    if row is not None:
        row.last_seen_at = datetime.now(timezone.utc)
        if signal.fp_hash and not row.fp_hash:
            row.fp_hash = signal.fp_hash
        session.add(row)
        await session.flush()
        return row
    row = DemoDeviceQuota(
        device_key=signal.device_key,
        ip_hash=signal.ip_hash,
        ua_hash=signal.ua_hash,
        fp_hash=signal.fp_hash,
        demo_used_count=0,
    )
    session.add(row)
    await session.flush()
    return row


async def device_demo_slots_remaining(
    session: AsyncSession,
    device_key: str | None,
) -> int:
    limit = demo_device_limit()
    if limit <= 0:
        return 0
    if not device_key:
        return limit
    row = await session.scalar(
        select(DemoDeviceQuota.demo_used_count).where(DemoDeviceQuota.device_key == device_key)
    )
    used = int(row or 0)
    return max(0, limit - used)


async def demo_grant_for_device(
    session: AsyncSession,
    signal: DeviceSignal | None,
    *,
    default_grant: int,
) -> int:
    grant = max(0, int(default_grant))
    if grant <= 0:
        return 0
    if signal is None:
        return grant
    remaining = await device_demo_slots_remaining(session, signal.device_key)
    return min(grant, remaining)


async def try_consume_device_demo_slot(
    session: AsyncSession,
    signal: DeviceSignal,
    *,
    user_id: int | None = None,
) -> bool:
    limit = demo_device_limit()
    if limit <= 0:
        return False
    stmt = (
        select(DemoDeviceQuota)
        .where(DemoDeviceQuota.device_key == signal.device_key)
        .with_for_update()
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = DemoDeviceQuota(
            device_key=signal.device_key,
            ip_hash=signal.ip_hash,
            ua_hash=signal.ua_hash,
            fp_hash=signal.fp_hash,
            demo_used_count=0,
        )
        session.add(row)
        await session.flush()
        stmt = (
            select(DemoDeviceQuota)
            .where(DemoDeviceQuota.device_key == signal.device_key)
            .with_for_update()
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return False
    if int(row.demo_used_count or 0) >= limit:
        return False
    row.demo_used_count = int(row.demo_used_count or 0) + 1
    row.last_user_id = user_id
    row.last_seen_at = datetime.now(timezone.utc)
    if signal.fp_hash and not row.fp_hash:
        row.fp_hash = signal.fp_hash
    session.add(row)
    await session.flush()
    return True
