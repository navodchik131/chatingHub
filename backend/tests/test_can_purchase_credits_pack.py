from datetime import datetime, timedelta, timezone

from app.db.models import Subscription, SubscriptionStatus
from app.services.billing_plan import can_purchase_credits_pack


def _sub(*, plan: str, status: SubscriptionStatus, period_end: datetime | None = None) -> Subscription:
    return Subscription(
        user_id=1,
        billing_plan=plan,
        status=status,
        current_period_end=period_end,
    )


def test_credits_plan_can_always_purchase() -> None:
    assert can_purchase_credits_pack("credits", None) is True
    assert can_purchase_credits_pack("credits", _sub(plan="credits", status=SubscriptionStatus.none)) is True


def test_pro_active_subscription_can_purchase() -> None:
    end = datetime.now(timezone.utc) + timedelta(days=10)
    sub = _sub(plan="pro", status=SubscriptionStatus.active, period_end=end)
    assert can_purchase_credits_pack("pro", sub) is True
    assert can_purchase_credits_pack("byok", sub) is True


def test_pro_without_active_subscription_cannot_purchase() -> None:
    sub = _sub(plan="pro", status=SubscriptionStatus.none)
    assert can_purchase_credits_pack("pro", sub) is False


def test_standard_active_subscription_can_purchase() -> None:
    end = datetime.now(timezone.utc) + timedelta(days=10)
    sub = _sub(plan="standard", status=SubscriptionStatus.active, period_end=end)
    assert can_purchase_credits_pack("standard", sub) is True
