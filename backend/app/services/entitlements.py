from __future__ import annotations

"""Совместимость: раньше активная подписка освобождала от списания кредитов в студии. Сейчас кредиты привязаны к тарифу managed/BYOK в студии."""

from datetime import datetime, timezone

from app.db.models import Subscription, SubscriptionStatus


def subscription_active(sub: Subscription | None) -> bool:
    if sub is None:
        return False
    if sub.status not in (SubscriptionStatus.active, SubscriptionStatus.trialing):
        return False
    end = sub.current_period_end
    if end is not None:
        now = datetime.now(timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end < now:
            return False
    return True


def subscription_covers_usage(sub: Subscription | None) -> bool:
    """Устарело: не используется для списания кредитов студии."""
    return False
