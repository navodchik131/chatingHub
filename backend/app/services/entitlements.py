from __future__ import annotations

from app.db.models import Subscription, SubscriptionStatus


def subscription_covers_usage(sub: Subscription | None) -> bool:
    if sub is None:
        return False
    return sub.status in (SubscriptionStatus.active, SubscriptionStatus.trialing)
