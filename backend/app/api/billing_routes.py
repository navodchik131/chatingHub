from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.db.models import CreditAccount, Subscription, User
from app.db.session import get_session
from app.schemas import (
    BillingCreditsPricingOut,
    BillingPlanItemOut,
    BillingPlansOut,
    SubscribeWithCreditsIn,
    SubscribeWithCreditsOut,
    YookassaPaymentCreateIn,
    YookassaPaymentOut,
)
from app.services.billing_credits import (
    assert_credits_quantity_allowed,
    credit_unit_price_rub,
    credits_amount_yookassa_value,
    credits_total_rub,
    rub_to_credits_ceil,
)
from app.services.billing_subscription import activate_subscription_product
from app.services.credits import ensure_can_consume_credits, record_usage
from app.services.entitlements import subscription_is_paid_active
from app.services.billing_plan import normalize_billing_plan, platform_covers_studio_api_costs
from app.services.plan_catalog import (
    catalog_public_dict,
    get_plan_spec,
    list_subscription_products,
    managed_period_credits,
    resolve_product_id,
)
from app.services.workspace import is_workspace_owner, workspace_owner_id
from app.services.yookassa_apply import apply_yookassa_payment_succeeded
from app.services.yookassa_client import create_payment, parse_notification_body

log = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def _rub_amount_str(amount_rub: int) -> str:
    return f"{max(0, int(amount_rub))}.00"


@router.get("/plans", response_model=BillingPlansOut)
async def billing_plans() -> BillingPlansOut:
    items: list[BillingPlanItemOut] = []
    for spec in list_subscription_products():
        period_label = "год" if spec.period == "year" else "мес."
        period_credits = managed_period_credits(spec)
        bonus = f", +{period_credits} кр." if period_credits else ""
        items.append(
            BillingPlanItemOut(
                product=spec.product,
                title=f"{spec.title_ru} — {period_label}{bonus}",
                price_rub=spec.price_rub,
            )
        )
    items.append(
        BillingPlanItemOut(
            product="credits_pack",
            title="Кредиты студии — любое количество от 50 шт.",
            price_rub=int(credits_total_rub(settings.billing_credits_min_purchase)),
            credits_pricing=BillingCreditsPricingOut(
                min_quantity=settings.billing_credits_min_purchase,
                bulk_from=settings.billing_credits_bulk_from,
                unit_price_rub=float(settings.billing_credits_unit_price_rub),
                bulk_unit_price_rub=float(settings.billing_credits_bulk_unit_price_rub),
            ),
        )
    )
    return BillingPlansOut(items=items, catalog=catalog_public_dict())


@router.post("/subscribe-with-credits", response_model=SubscribeWithCreditsOut)
async def subscribe_with_credits(
    body: SubscribeWithCreditsIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> SubscribeWithCreditsOut:
    if not is_workspace_owner(user):
        raise HTTPException(
            status_code=403,
            detail="Оплата доступна только владельцу аккаунта",
        )
    product = resolve_product_id(body.product.strip())
    spec = get_plan_spec(product)
    if spec is None:
        raise HTTPException(status_code=400, detail="Неизвестный тариф")

    billing_uid = workspace_owner_id(user)
    cost = rub_to_credits_ceil(spec.price_rub)
    billing = await ensure_can_consume_credits(session, user, cost)
    await record_usage(
        session,
        user,
        billing,
        "subscription_credits_payment",
        cost,
        meta={"product": product, "price_rub": spec.price_rub},
    )
    ref = f"credits:{billing_uid}:{product}"
    result = await activate_subscription_product(
        session,
        billing_uid,
        product,
        payment_ref=ref,
        payment_kind="credits",
        payment_amount_rub=spec.price_rub,
    )
    acc = await session.get(CreditAccount, billing_uid)
    balance_after = int(acc.balance) if acc else 0
    await session.commit()
    return SubscribeWithCreditsOut(
        product=result["product"],
        credits_spent=cost,
        price_rub=result["price_rub"],
        balance_after=balance_after,
        managed_bonus_credits=result["managed_bonus_credits"],
    )


@router.get("/catalog")
async def billing_catalog() -> dict:
    return {
        **catalog_public_dict(),
        "signup_bonus_credits": settings.signup_bonus_credits,
        "credits_pricing": {
            "min_quantity": settings.billing_credits_min_purchase,
            "bulk_from": settings.billing_credits_bulk_from,
            "unit_price_rub": float(settings.billing_credits_unit_price_rub),
            "bulk_unit_price_rub": float(settings.billing_credits_bulk_unit_price_rub),
        },
        "marketing_beta_creators_count": settings.marketing_beta_creators_count,
    }


@router.post("/yookassa/payment", response_model=YookassaPaymentOut)
async def yookassa_start_payment(
    body: YookassaPaymentCreateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> YookassaPaymentOut:
    if not is_workspace_owner(user):
        raise HTTPException(
            status_code=403,
            detail="Оплата доступна только владельцу аккаунта",
        )
    if not settings.yookassa_configured:
        raise HTTPException(status_code=503, detail="ЮKassa не настроена на сервере")

    billing_uid = workspace_owner_id(user)
    product = resolve_product_id(body.product)

    if body.product == "credits_pack":
        sub_row = await session.scalar(
            select(Subscription).where(Subscription.user_id == billing_uid)
        )
        plan = normalize_billing_plan(sub_row.billing_plan if sub_row else None)
        if not subscription_is_paid_active(sub_row) or not platform_covers_studio_api_costs(plan):
            raise HTTPException(
                status_code=402,
                detail="Покупка кредитов доступна после оплаты подписки Managed.",
            )
        q = body.credits_quantity
        assert q is not None
        try:
            assert_credits_quantity_allowed(q)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        amount_value = credits_amount_yookassa_value(q)
        desc = f"Кредиты студии ({q} шт.)"
        meta_product = "credits_pack"
    else:
        spec = get_plan_spec(product)
        if spec is None:
            raise HTTPException(status_code=400, detail="Неизвестный продукт")
        price = spec.price_rub
        period = "год" if spec.period == "year" else "30 дн."
        desc = f"Подписка ModelMate ({spec.title_ru}), {period}"
        amount_value = _rub_amount_str(price)
        meta_product = spec.product

    base = settings.public_app_url.rstrip("/")
    return_url = f"{base}{settings.billing_success_path}"

    meta: dict[str, str] = {"user_id": str(billing_uid), "product": meta_product}
    if body.product == "credits_pack":
        meta["credits_quantity"] = str(body.credits_quantity)

    try:
        pay = await create_payment(
            amount_value=amount_value,
            description=desc[:210],
            return_url=return_url,
            metadata=meta,
        )
    except RuntimeError as e:
        log.warning("yookassa create_payment: %s", e)
        raise HTTPException(status_code=502, detail="Не удалось создать платёж в ЮKassa") from e

    pid = str(pay.get("id") or "").strip()
    conf = pay.get("confirmation") if isinstance(pay.get("confirmation"), dict) else {}
    url = str(conf.get("confirmation_url") or "").strip()
    if not pid or not url:
        raise HTTPException(status_code=502, detail="ЮKassa вернула неполный ответ")
    return YookassaPaymentOut(payment_id=pid, confirmation_url=url)


@router.post("/yookassa/webhook")
async def yookassa_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    wh_secret = (settings.yookassa_webhook_secret or "").strip()
    if wh_secret:
        got = (request.query_params.get("secret") or "").strip() or (
            request.headers.get("X-YooKassa-Webhook-Secret") or ""
        ).strip()
        if got != wh_secret:
            raise HTTPException(status_code=403, detail="webhook secret")

    raw = await request.body()
    data = parse_notification_body(raw)
    if not data:
        raise HTTPException(status_code=400, detail="invalid json")

    event = (data.get("event") or "").strip()
    if event != "payment.succeeded":
        return {"ok": True, "ignored": event or "unknown"}

    obj = data.get("object")
    if not isinstance(obj, dict):
        raise HTTPException(status_code=400, detail="invalid object")

    if (obj.get("status") or "").strip() != "succeeded":
        return {"ok": True, "skipped": obj.get("status")}

    result = await apply_yookassa_payment_succeeded(session, payment_object=obj)
    log.info("yookassa webhook: %s", result)
    return result
