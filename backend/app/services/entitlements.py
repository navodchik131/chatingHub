from __future__ import annotations

"""Совместимость: раньше активная подписка освобождала от списания кредитов в студии. Сейчас кредиты привязаны к тарифу managed/BYOK в студии."""

from datetime import datetime, timezone

from app.db.models import Subscription, SubscriptionStatus


def _subscription_period_not_expired(sub: Subscription) -> bool:
    end = sub.current_period_end
    if end is None:
        return True
    now = datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return end >= now


def subscription_active(sub: Subscription | None) -> bool:
    if sub is None:
        return False
    if sub.status not in (SubscriptionStatus.active, SubscriptionStatus.trialing):
        return False
    return _subscription_period_not_expired(sub)


def subscription_is_onboarding_trial(sub: Subscription | None) -> bool:
    """Оплата ещё не прошла (стадия после регистрации при включённой ЮKassa)."""
    return sub is not None and sub.status == SubscriptionStatus.trialing


def subscription_is_paid_active(sub: Subscription | None) -> bool:
    """Оплаченная подписка (не trialing), период не истёк."""
    if sub is None or sub.status != SubscriptionStatus.active:
        return False
    return _subscription_period_not_expired(sub)


def subscription_covers_usage(sub: Subscription | None) -> bool:
    """Устарело: не используется для списания кредитов студии."""
    return False
