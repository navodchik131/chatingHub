from datetime import datetime, timedelta, timezone

from app.db.models import Subscription, SubscriptionStatus
from app.services.billing_plan import plan_allows_chat, plan_allows_companion
from app.services.plan_entitlements import (
    chat_allowed_for_subscription,
    companion_allowed_for_subscription,
)


def _sub(
    *,
    plan: str,
    tier: str = "solo",
    status: SubscriptionStatus = SubscriptionStatus.active,
    period_end: datetime | None = None,
) -> Subscription:
    end = period_end or (datetime.now(timezone.utc) + timedelta(days=10))
    return Subscription(
        user_id=1,
        billing_plan=plan,
        plan_tier=tier,
        status=status,
        current_period_end=end,
    )


def test_plan_allows_chat_on_standard_pro() -> None:
    assert plan_allows_chat("standard") is True
    assert plan_allows_chat("pro") is True
    assert plan_allows_chat("credits") is False


def test_plan_allows_companion_only_studio() -> None:
    assert plan_allows_companion("standard", "studio") is True
    assert plan_allows_companion("pro", "studio") is True
    assert plan_allows_companion("standard", "solo") is False
    assert plan_allows_companion("pro", "pro") is False
    assert plan_allows_companion("credits", "studio") is False
    assert plan_allows_companion("standard", None) is False


def test_chat_allowed_on_any_paid_plan() -> None:
    assert chat_allowed_for_subscription(_sub(plan="standard", tier="solo")) is True
    assert chat_allowed_for_subscription(_sub(plan="pro", tier="pro")) is True
    assert chat_allowed_for_subscription(_sub(plan="standard", tier="studio")) is True
    assert chat_allowed_for_subscription(_sub(plan="credits", tier="solo", status=SubscriptionStatus.none)) is False


def test_companion_allowed_requires_active_studio() -> None:
    assert companion_allowed_for_subscription(None) is False
    assert companion_allowed_for_subscription(_sub(plan="standard", tier="solo")) is False
    assert companion_allowed_for_subscription(_sub(plan="pro", tier="pro")) is False
    assert companion_allowed_for_subscription(_sub(plan="standard", tier="studio")) is True
    assert companion_allowed_for_subscription(_sub(plan="pro", tier="studio")) is True
    assert (
        companion_allowed_for_subscription(
            _sub(plan="standard", tier="studio", status=SubscriptionStatus.none)
        )
        is False
    )
