from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.db.models import Subscription, SubscriptionStatus, User
from app.db.session import get_session
from app.services.workspace import is_workspace_owner

log = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

try:
    import stripe
except ImportError:  # pragma: no cover
    stripe = None


@router.post("/checkout")
async def create_checkout(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    if not is_workspace_owner(user):
        raise HTTPException(
            status_code=403,
            detail="Оформление подписки доступно только владельцу аккаунта",
        )
    if stripe is None or not settings.stripe_secret_key.strip():
        raise HTTPException(status_code=503, detail="Stripe не настроен на сервере")
    if not settings.stripe_price_subscription.strip():
        raise HTTPException(status_code=503, detail="Не задан STRIPE_PRICE_SUBSCRIPTION")

    stripe.api_key = settings.stripe_secret_key

    sub = user.subscription
    if sub is None:
        sub = Subscription(user_id=user.id, status=SubscriptionStatus.none)
        session.add(sub)
        await session.flush()
        user.subscription = sub

    customer_id = (sub.stripe_customer_id or "").strip()
    if not customer_id:
        cust = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": str(user.id)},
        )
        sub.stripe_customer_id = cust.id
        await session.commit()
        customer_id = cust.id

    base = settings.public_app_url.rstrip("/")
    success = f"{base}{settings.billing_success_path}"
    cancel = f"{base}{settings.billing_cancel_path}"

    sess = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": settings.stripe_price_subscription, "quantity": 1}],
        success_url=success,
        cancel_url=cancel,
        metadata={"user_id": str(user.id)},
    )
    if not sess.url:
        raise HTTPException(status_code=500, detail="Stripe не вернул URL")
    return {"url": sess.url}


@router.post("/stripe-webhook")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if stripe is None:
        raise HTTPException(status_code=503, detail="Stripe SDK не установлен")
    if not settings.stripe_webhook_secret.strip():
        raise HTTPException(status_code=503, detail="Stripe webhook не настроен")

    payload = await request.body()
    sig = request.headers.get("stripe-signature") or ""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except Exception as e:
        log.warning("stripe webhook verify failed: %s", e)
        raise HTTPException(status_code=400, detail="invalid signature") from e

    et = event.get("type")
    data = event.get("data", {}).get("object", {})

    if et == "checkout.session.completed":
        meta = data.get("metadata") or {}
        uid_s = meta.get("user_id") or data.get("client_reference_id")
        if not uid_s:
            return {"ok": True, "skipped": "no user"}
        user_id = int(uid_s)
        sub_id = data.get("subscription")
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        r = await session.execute(stmt)
        sub = r.scalar_one_or_none()
        if sub:
            sub.stripe_subscription_id = str(sub_id) if sub_id else sub.stripe_subscription_id
            sub.status = SubscriptionStatus.active
            sub.plan_tier = "standard"
            sub.current_period_end = datetime.now(timezone.utc)
            await session.commit()

    elif et in ("customer.subscription.updated", "customer.subscription.deleted"):
        sub_obj = data
        st = sub_obj.get("status")
        stripe_sub_id = sub_obj.get("id")
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_sub_id
        )
        r = await session.execute(stmt)
        sub = r.scalar_one_or_none()
        if sub and isinstance(st, str):
            mapping = {
                "active": SubscriptionStatus.active,
                "trialing": SubscriptionStatus.trialing,
                "past_due": SubscriptionStatus.past_due,
                "canceled": SubscriptionStatus.canceled,
                "unpaid": SubscriptionStatus.unpaid,
            }
            sub.status = mapping.get(st, SubscriptionStatus.none)
            await session.commit()

    return {"ok": True}
