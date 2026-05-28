"""Реферальная программа: код приглашения и бонусы."""

from __future__ import annotations

import json
import logging
import secrets
import string
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditAccount, UsageEvent, User
from app.services.billing_credits import (
    credit_unit_price_rub,
    referrer_reward_credits_from_payment_rub,
)
log = logging.getLogger(__name__)

REFERRER_REWARD_KIND = "referral_referrer_reward"


def generate_referral_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


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
    """Привязка реферера и 25 кр. приглашённому. Возвращает referrer_id или None."""
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
            acc = new_owner.credit_account
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
    session: AsyncSession,
    referred_owner_id: int,
    *,
    trigger_product: str = "",
    payment_amount_rub: Decimal | None = None,
) -> None:
    """Бонус рефереру: % от каждой оплаты приглашённого в кредитах (курс 1 кр. = unit ₽)."""
    referred = await session.get(User, referred_owner_id)
    if not referred or not referred.referred_by_user_id:
        return
    referrer_id = referred.referred_by_user_id

    amount = payment_amount_rub if payment_amount_rub is not None else Decimal(0)
    reward = referrer_reward_credits_from_payment_rub(amount)
    if reward <= 0:
        log.info(
            "referral skip zero reward referrer=%s referred=%s amount_rub=%s",
            referrer_id,
            referred_owner_id,
            amount,
        )
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
            kind=REFERRER_REWARD_KIND,
            credits_delta=reward,
            meta=json.dumps(
                {
                    "referred_user_id": referred_owner_id,
                    "trigger_product": (trigger_product or "")[:64],
                    "payment_amount_rub": str(amount),
                    "percent": settings.referral_referrer_payment_percent,
                },
                ensure_ascii=False,
            ),
        )
    )
    log.info(
        "referral reward referrer=%s referred=%s credits=%s from_rub=%s",
        referrer_id,
        referred_owner_id,
        reward,
        amount,
    )


def referrer_reward_summary_text() -> str:
    pub = referral_public_dict()
    pct = pub["referrer_payment_percent"]
    unit = pub["credit_unit_price_rub"]
    ex_rub = pub["referrer_reward_example_rub"]
    ex_cr = pub["referrer_reward_example_credits"]
    return (
        f"{pct}% с каждой оплаты приглашённого в кредитах (1 кр. = {unit:g} ₽; "
        f"пример: {ex_rub} ₽ → ~{ex_cr} кр. за платёж)"
    )


def referral_public_dict() -> dict:
    unit = float(credit_unit_price_rub())
    pct = int(settings.referral_referrer_payment_percent)
    friend = max(0, int(settings.referral_signup_bonus_credits))
    base = max(0, int(settings.signup_bonus_credits))
    example_rub = 990
    example_credits = referrer_reward_credits_from_payment_rub(Decimal(example_rub))
    return {
        "friend_referral_credits": friend,
        "signup_base_credits": base,
        "referrer_payment_percent": pct,
        "credit_unit_price_rub": unit,
        "referrer_reward_example_rub": example_rub,
        "referrer_reward_example_credits": example_credits,
    }


async def referral_stats(session: AsyncSession, owner_id: int) -> dict:
    invited = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.referred_by_user_id == owner_id)
        )
        or 0
    )
    credits = int(
        await session.scalar(
            select(func.coalesce(func.sum(UsageEvent.credits_delta), 0)).where(
                UsageEvent.user_id == owner_id,
                UsageEvent.kind == REFERRER_REWARD_KIND,
            )
        )
        or 0
    )
    return {"invited_count": invited, "credits_earned": credits}
