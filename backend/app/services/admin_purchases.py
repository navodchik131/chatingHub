"""Список платных покупок на платформе (подписки и кредиты) для админки."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageEvent, User
from app.services.admin_analytics import _parse_usage_meta, _usage_event_revenue_rub
from app.services.plan_catalog import get_plan_spec, resolve_product_id

# Только события «деньги / покупка», без бонусных начислений подписки.
_PURCHASE_KINDS = (
    "subscription_payment",
    "yookassa_credits_pack",
    "tribute_credits_pack",
    "tribute_subscription_renewed",
)


def _utc_range(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    """Включительно from_date … to_date по UTC (конец to_date — 23:59:59.999)."""
    start = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def _product_label(product: str | None) -> str:
    if not product:
        return "—"
    resolved = resolve_product_id(str(product))
    spec = get_plan_spec(resolved)
    if spec and spec.title_ru:
        return spec.title_ru
    return resolved


def _purchase_type(kind: str) -> str:
    if kind == "subscription_payment":
        return "subscription"
    if kind in ("yookassa_credits_pack", "tribute_credits_pack"):
        return "credits"
    if kind == "tribute_subscription_renewed":
        return "subscription_renewal"
    return "other"


def _payment_provider(kind: str, meta: dict[str, Any]) -> str:
    pk = str(meta.get("payment_kind") or "").strip().lower()
    if pk == "yookassa":
        return "yookassa"
    if pk == "tribute":
        return "tribute"
    if pk == "credits":
        return "credits"
    if kind.startswith("yookassa_"):
        return "yookassa"
    if kind.startswith("tribute_"):
        return "tribute"
    return "unknown"


def _int_meta(meta: dict[str, Any], key: str) -> int | None:
    raw = meta.get(key)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _usage_event_to_purchase(
    ev: UsageEvent,
    *,
    user_email: str | None,
) -> dict[str, Any]:
    meta = _parse_usage_meta(ev.meta)
    kind = str(ev.kind or "")
    product = meta.get("product")
    if kind in ("yookassa_credits_pack", "tribute_credits_pack"):
        product = product or "credits_pack"
    amount_rub = _usage_event_revenue_rub(kind, meta)
    return {
        "id": ev.id,
        "user_id": ev.user_id,
        "user_email": user_email,
        "created_at": ev.created_at,
        "kind": kind,
        "purchase_type": _purchase_type(kind),
        "product_id": str(product) if product else None,
        "product_label": _product_label(str(product) if product else None),
        "payment_provider": _payment_provider(kind, meta),
        "amount_rub": amount_rub,
        "credits_quantity": _int_meta(meta, "credits_quantity"),
        "credits_granted": _int_meta(meta, "credits_granted"),
        "payment_ref": (meta.get("payment_ref") or meta.get("payment_id") or None),
    }


async def list_admin_purchases(
    session: AsyncSession,
    *,
    from_date: date,
    to_date: date,
    skip: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    if to_date < from_date:
        raise ValueError("to_date must be >= from_date")
    start, end = _utc_range(from_date, to_date)
    lim = max(1, min(int(limit), 500))
    off = max(0, int(skip))

    base = (
        select(UsageEvent, User.email)
        .join(User, User.id == UsageEvent.user_id)
        .where(
            UsageEvent.kind.in_(_PURCHASE_KINDS),
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        .order_by(UsageEvent.created_at.desc(), UsageEvent.id.desc())
    )

    # Сводка по всему периоду (без пагинации).
    all_rows = (await session.execute(base)).all()
    items_all: list[dict[str, Any]] = []
    total_rub = 0
    sub_count = 0
    credits_count = 0
    for ev, email in all_rows:
        row = _usage_event_to_purchase(ev, user_email=email)
        items_all.append(row)
        total_rub += int(row["amount_rub"] or 0)
        pt = row["purchase_type"]
        if pt in ("subscription", "subscription_renewal"):
            sub_count += 1
        elif pt == "credits":
            credits_count += 1

    page_slice = items_all[off : off + lim + 1]
    has_more = len(page_slice) > lim
    page_items = page_slice[:lim]

    return {
        "from_date": from_date,
        "to_date": to_date,
        "skip": off,
        "has_more": has_more,
        "items": page_items,
        "summary": {
            "total_count": len(items_all),
            "total_amount_rub": total_rub,
            "subscription_count": sub_count,
            "credits_count": credits_count,
        },
    }
