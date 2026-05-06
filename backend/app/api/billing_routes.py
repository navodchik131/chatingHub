from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.db.models import User
from app.db.session import get_session
from app.schemas import (
    BillingPlanItemOut,
    BillingPlansOut,
    YookassaPaymentCreateIn,
    YookassaPaymentOut,
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
    return BillingPlansOut(
        items=[
            BillingPlanItemOut(
                product="sub_managed_month",
                title="Подписка Managed — ключи платформы, кредиты на студию",
                price_rub=settings.billing_price_managed_month_rub,
            ),
            BillingPlanItemOut(
                product="sub_byok_month",
                title="Подписка BYOK — свои LLM и WaveSpeed, кредиты на студию не списываются",
                price_rub=settings.billing_price_byok_month_rub,
            ),
            BillingPlanItemOut(
                product="credits_pack",
                title=f"Пакет кредитов ({settings.billing_credit_pack_credits} шт.)",
                price_rub=settings.billing_credit_pack_price_rub,
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

    if body.product == "sub_managed_month":
        price = settings.billing_price_managed_month_rub
        desc = "Подписка Chating Hub (Managed), 30 дн."
    elif body.product == "sub_byok_month":
        price = settings.billing_price_byok_month_rub
        desc = "Подписка Chating Hub (BYOK), 30 дн."
    else:
        price = settings.billing_credit_pack_price_rub
        desc = f"Пакет кредитов ({settings.billing_credit_pack_credits})"

    base = settings.public_app_url.rstrip("/")
    return_url = f"{base}{settings.billing_success_path}"

    billing_uid = workspace_owner_id(user)
    meta = {"user_id": str(billing_uid), "product": body.product}

    try:
        pay = await create_payment(
            amount_value=_rub_amount_str(price),
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
