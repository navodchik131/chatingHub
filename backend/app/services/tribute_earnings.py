"""Агрегация дохода Tribute для владельца и чатеров (доля 20%)."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import TributeEarningEvent, User
from app.services.workspace import is_workspace_owner, workspace_owner_id
from app.services.workspace_model_access import member_allowed_studio_model_ids


def chatter_share_ratio() -> float:
    pct = int(settings.tribute_chatter_share_percent)
    return max(0.0, min(100.0, float(pct))) / 100.0


def _period_bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(to_date, time.max, tzinfo=timezone.utc)
    return start, end


async def aggregate_tribute_earnings(
    session: AsyncSession,
    *,
    viewer: User,
    from_date: date,
    to_date: date,
) -> dict:
    if to_date < from_date:
        from_date, to_date = to_date, from_date

    owner_id = workspace_owner_id(viewer)
    start, end = _period_bounds(from_date, to_date)
    allowed_models = await member_allowed_studio_model_ids(session, viewer)

    stmt = (
        select(
            TributeEarningEvent.currency,
            func.coalesce(func.sum(TributeEarningEvent.amount_minor), 0),
        )
        .where(
            TributeEarningEvent.user_id == owner_id,
            TributeEarningEvent.occurred_at >= start,
            TributeEarningEvent.occurred_at <= end,
        )
        .group_by(TributeEarningEvent.currency)
    )
    if allowed_models is not None:
        if not allowed_models:
            return _empty_summary(from_date, to_date, viewer)
        stmt = stmt.where(TributeEarningEvent.studio_model_id.in_(allowed_models))

    rows = list((await session.execute(stmt)).all())
    if not rows:
        return _empty_summary(from_date, to_date, viewer)

    by_currency: dict[str, int] = {}
    gross_total = 0
    for currency, total in rows:
        cur = str(currency or "USD").upper()
        minor = int(total or 0)
        by_currency[cur] = by_currency.get(cur, 0) + minor
        gross_total += minor

    ratio = 1.0 if is_workspace_owner(viewer) else chatter_share_ratio()
    display_by_currency = {
        cur: int(round(amount * ratio)) for cur, amount in by_currency.items()
    }
    display_total = int(round(gross_total * ratio))

    count_stmt = select(func.count()).select_from(TributeEarningEvent).where(
        TributeEarningEvent.user_id == owner_id,
        TributeEarningEvent.occurred_at >= start,
        TributeEarningEvent.occurred_at <= end,
    )
    if allowed_models is not None:
        count_stmt = count_stmt.where(
            TributeEarningEvent.studio_model_id.in_(allowed_models)
        )
    event_count = int(await session.scalar(count_stmt) or 0)

    primary_currency = max(by_currency.items(), key=lambda x: abs(x[1]))[0]

    return {
        "from_date": from_date,
        "to_date": to_date,
        "is_owner": is_workspace_owner(viewer),
        "chatter_share_percent": int(settings.tribute_chatter_share_percent),
        "gross_minor": gross_total,
        "display_minor": display_total,
        "currency": primary_currency,
        "by_currency": display_by_currency,
        "gross_by_currency": by_currency,
        "event_count": event_count,
    }


def _empty_summary(from_date: date, to_date: date, viewer: User) -> dict:
    return {
        "from_date": from_date,
        "to_date": to_date,
        "is_owner": is_workspace_owner(viewer),
        "chatter_share_percent": int(settings.tribute_chatter_share_percent),
        "gross_minor": 0,
        "display_minor": 0,
        "currency": "USD",
        "by_currency": {},
        "gross_by_currency": {},
        "event_count": 0,
    }
