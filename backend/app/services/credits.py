from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CreditAccount, UsageEvent, User
from app.services.entitlements import subscription_covers_usage
from app.services.workspace import resolve_billing_user

log = logging.getLogger(__name__)


async def ensure_can_consume_credits(
    session: AsyncSession, actor: User, cost: int
) -> User:
    """Проверяет лимит по биллингу владельца; возвращает billing user."""
    if cost <= 0:
        return await resolve_billing_user(session, actor)
    billing = await resolve_billing_user(session, actor)
    if subscription_covers_usage(billing.subscription):
        return billing
    bal = billing.credit_account.balance if billing.credit_account else 0
    if bal < cost:
        raise HTTPException(
            status_code=402,
            detail="Нужна активная подписка или больше кредитов. Пополните баланс или оформите подписку.",
        )
    return billing


async def record_usage(
    session: AsyncSession,
    actor: User,
    billing: User,
    kind: str,
    credits: int,
    meta: dict[str, Any] | None = None,
) -> None:
    """Списывает кредиты с владельца; в usage_events — владелец, в meta может быть actor."""
    covered = subscription_covers_usage(billing.subscription)
    delta = 0 if covered else -abs(credits)
    meta_full = dict(meta or {})
    if actor.id != billing.id:
        meta_full["actor_user_id"] = actor.id
    if not covered and credits > 0:
        acc = await session.get(CreditAccount, billing.id)
        if acc is None:
            acc = CreditAccount(user_id=billing.id, balance=0)
            session.add(acc)
            await session.flush()
        if acc.balance < credits:
            raise HTTPException(status_code=402, detail="Недостаточно кредитов")
        acc.balance -= credits
        delta = -credits

    ev = UsageEvent(
        user_id=billing.id,
        kind=kind,
        credits_delta=delta,
        meta=json.dumps(meta_full, ensure_ascii=False) if meta_full else None,
    )
    session.add(ev)
    await session.flush()
    if not covered and credits > 0:
        log.debug(
            "credits spent billing=%s actor=%s kind=%s amount=%s",
            billing.id,
            actor.id,
            kind,
            credits,
        )
