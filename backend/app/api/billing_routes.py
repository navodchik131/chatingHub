from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.db.models import Subscription, User
from app.db.session import get_session
from app.schemas import (
    BillingCreditsPricingOut,
    BillingPlanItemOut,
    BillingPlansOut,
    YookassaPaymentCreateIn,
    YookassaPaymentOut,
)
from app.services.billing_credits import (
    assert_credits_quantity_allowed,
    credits_amount_yookassa_value,
    credits_total_rub,
)
from app.services.entitlements import subscription_is_paid_active
from app.services.billing_plan import normalize_billing_plan, platform_covers_studio_api_costs
from app.services.workspace import is_workspace_owner, workspace_owner_id
from app.services.yookassa_apply import apply_yookassa_payment_succeeded
from app.services.yookassa_client import create_payment, parse_notification_body

log = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def _rub_amount_str(amount_rub: int) -> str:
    return f"{max(0, int(amount_rub))}.00"


@router.get("/plans", response_model=BillingPlansOut)
async def billing_plans() -> BillingPlansOut:
    return BillingPlansOut(
        items=[
            BillingPlanItemOut(
                product="sub_managed_month",
                title="Подписка Managed — ключи платформы, кредиты на студию",
                price_rub=settings.billing_price_managed_month_rub,
            ),
            BillingPlanItemOut(
                product="sub_byok_month",
                title="Подписка BYOK — свой WaveSpeed для картинок; LLM студии на сервере; кредиты не списываются",
                price_rub=settings.billing_price_byok_month_rub,
            ),
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
            ),
        ]
    )


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

    if body.product == "sub_managed_month":
        price = settings.billing_price_managed_month_rub
        desc = "Подписка Chating Hub (Managed), 30 дн."
    elif body.product == "sub_byok_month":
        price = settings.billing_price_byok_month_rub
        desc = "Подписка Chating Hub (BYOK), 30 дн."
    elif body.product == "credits_pack":
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
    else:
        raise HTTPException(status_code=400, detail="Неизвестный продукт")

    base = settings.public_app_url.rstrip("/")
    return_url = f"{base}{settings.billing_success_path}"

    meta: dict[str, str] = {"user_id": str(billing_uid), "product": body.product}
    if body.product == "credits_pack":
        meta["credits_quantity"] = str(body.credits_quantity)

    try:
        pay = await create_payment(
            amount_value=amount_value if body.product == "credits_pack" else _rub_amount_str(price),
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
