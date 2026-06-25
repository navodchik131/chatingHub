"""Пока онлайн-оплата (ЮKassa) не подключена, владельцы могут автоматически получать стартовый Managed-доступ."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Subscription, SubscriptionStatus
from app.services.billing_plan import BILLING_PLAN_PRO, BILLING_PLAN_STANDARD, normalize_billing_plan


def starter_managed_effective() -> bool:
    """
    True — новые и существующие владельцы без оплаты получают активную подписку Managed
    (ключи LLM и WaveSpeed с сервера, списание кредитов по правилам managed).
    Отключается, когда в .env настроены shop_id и секрет ЮKassa.
    """
    if not settings.billing_auto_starter_managed_without_payment:
        return False
    return not settings.yookassa_configured


async def ensure_starter_managed_subscription(session: AsyncSession, owner_id: int) -> bool:
    """
    Если режим стартера включён и у владельца подписка «пустая», выставляем active + managed.
    Не трогаем тариф BYOK. Возвращает True, если были изменения (нужен commit).
    """
    if not starter_managed_effective():
        return False

    sub = await session.scalar(select(Subscription).where(Subscription.user_id == owner_id))
    if not sub:
        session.add(
            Subscription(
                user_id=owner_id,
                status=SubscriptionStatus.active,
                billing_plan=BILLING_PLAN_STANDARD,
                plan_tier="solo",
            )
        )
        return True

    if sub.status != SubscriptionStatus.none:
        return False

    sub.status = SubscriptionStatus.active
    if normalize_billing_plan(sub.billing_plan) != BILLING_PLAN_PRO:
        sub.billing_plan = BILLING_PLAN_STANDARD
    return True
