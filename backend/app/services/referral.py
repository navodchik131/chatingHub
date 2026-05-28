"""Реферальная программа: код приглашения и бонусы."""

from __future__ import annotations

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditAccount, UsageEvent, User
from app.services.plan_entitlements import generate_referral_code

log = logging.getLogger(__name__)


async def ensure_owner_referral_code(session: AsyncSession, owner: User) -> str:
    if owner.parent_user_id is not None:
        raise ValueError("referral only for workspace owners")
    code = (getattr(owner, "referral_code", None) or "").strip()
    if code:
        return code
    for _ in range(12):
        candidate = generate_referral_code()
        dup = await session.scalar(
            select(User.id).where(User.referral_code == candidate)
        )
        if not dup:
            owner.referral_code = candidate
            await session.flush()
            return candidate
    raise RuntimeError("could not allocate referral code")


async def find_referrer_by_code(session: AsyncSession, code: str) -> User | None:
    c = (code or "").strip().upper()
    if not c:
        return None
    stmt = select(User).where(
        User.referral_code == c,
        User.parent_user_id.is_(None),
        User.is_active.is_(True),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def apply_referral_on_signup(
    session: AsyncSession,
    *,
    new_owner: User,
    referral_code: str | None,
) -> int | None:
    """Привязка реферера и бонус новому пользователю. Возвращает referrer_id или None."""
    ref_code = (referral_code or "").strip().upper()
    if not ref_code:
        return None
    referrer = await find_referrer_by_code(session, ref_code)
    if referrer is None or referrer.id == new_owner.id:
        return None
    new_owner.referred_by_user_id = referrer.id
    bonus = max(0, int(settings.referral_signup_bonus_credits))
    if bonus > 0:
        acc = await session.get(CreditAccount, new_owner.id)
        if acc is None:
            acc = CreditAccount(user_id=new_owner.id, balance=0)
            session.add(acc)
            await session.flush()
        acc.balance += bonus
        session.add(
            UsageEvent(
                user_id=new_owner.id,
                kind="referral_signup_bonus",
                credits_delta=bonus,
                meta=json.dumps(
                    {"referrer_id": referrer.id, "code": ref_code},
                    ensure_ascii=False,
                ),
            )
        )
    await session.flush()
    return referrer.id


async def grant_referrer_reward_if_needed(
    session: AsyncSession, referred_owner_id: int
) -> None:
    """Бонус рефереру при первой оплате приглашённого."""
    referred = await session.get(User, referred_owner_id)
    if not referred or not referred.referred_by_user_id:
        return
    referrer_id = referred.referred_by_user_id
    meta_match = await session.scalar(
        select(func.count())
        .select_from(UsageEvent)
        .where(
            UsageEvent.user_id == referrer_id,
            UsageEvent.kind == "referral_referrer_reward",
            UsageEvent.meta.contains(f'"referred_user_id": {referred_owner_id}'),
        )
    )
    if int(meta_match or 0) > 0:
        return
    reward = max(0, int(settings.referral_referrer_reward_credits))
    if reward <= 0:
        return
    acc = await session.get(CreditAccount, referrer_id)
    if acc is None:
        acc = CreditAccount(user_id=referrer_id, balance=0)
        session.add(acc)
        await session.flush()
    acc.balance += reward
    session.add(
        UsageEvent(
            user_id=referrer_id,
            kind="referral_referrer_reward",
            credits_delta=reward,
            meta=json.dumps(
                {"referred_user_id": referred_owner_id},
                ensure_ascii=False,
            ),
        )
    )
    log.info("referral reward referrer=%s referred=%s credits=%s", referrer_id, referred_owner_id, reward)


async def referral_stats(session: AsyncSession, owner_id: int) -> dict:
    invited = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.referred_by_user_id == owner_id)
        )
        or 0
    )
    rewards = int(
        await session.scalar(
            select(func.coalesce(func.sum(UsageEvent.credits_delta), 0))
            .where(
                UsageEvent.user_id == owner_id,
                UsageEvent.kind == "referral_referrer_reward",
            )
        )
        or 0
    )
    return {"invited_count": invited, "credits_earned": rewards}
