from __future__ import annotations

import json
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
    TributeCheckoutIn,
    TributeCheckoutOut,
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
from app.services.billing_plan import is_credits_plan, is_standard_plan, normalize_billing_plan
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
from app.connectors.tribute.signature import verify_tribute_webhook_signature
from app.services.telegram_identity import owner_telegram_linked
from app.services.tribute_billing_apply import apply_tribute_billing_webhook, tribute_billing_catalog
from app.services.tribute_billing_client import fetch_tribute_product

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
        can_buy = is_credits_plan(plan) or (
            is_standard_plan(plan) and subscription_is_paid_active(sub_row)
        )
        if not can_buy:
            raise HTTPException(
                status_code=402,
                detail=(
                    "Покупка кредитов доступна на тарифе Credits или при активной подписке Standard."
                ),
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


@router.post("/tribute/checkout", response_model=TributeCheckoutOut)
async def tribute_checkout(
    body: TributeCheckoutIn,
    user: User = Depends(get_current_user),
) -> TributeCheckoutOut:
    if not is_workspace_owner(user):
        raise HTTPException(
            status_code=403,
            detail="Оплата доступна только владельцу аккаунта",
        )
    if not settings.tribute_billing_configured:
        raise HTTPException(status_code=503, detail="Оплата через Tribute не настроена на сервере")
    if not owner_telegram_linked(user):
        raise HTTPException(
            status_code=400,
            detail="Привяжите Telegram в кабинете (Обзор) — без этого Tribute не сопоставит оплату с аккаунтом",
        )

    product = resolve_product_id(body.product.strip())
    catalog = tribute_billing_catalog()
    tribute_pid = catalog.tribute_product_id_for(
        product,
        credits_quantity=body.credits_quantity,
    )
    if tribute_pid is None:
        raise HTTPException(status_code=404, detail="Этот тариф не настроен для оплаты через Tribute")

    try:
        tribute_product = await fetch_tribute_product(
            tribute_pid,
            api_key=settings.tribute_billing_api_key,
        )
    except RuntimeError as e:
        log.warning("tribute checkout fetch product %s: %s", tribute_pid, e)
        raise HTTPException(status_code=502, detail="Не удалось получить товар из Tribute") from e

    web_link = str(tribute_product.get("webLink") or tribute_product.get("web_link") or "").strip()
    tg_link = str(tribute_product.get("link") or "").strip()
    if not web_link and not tg_link:
        raise HTTPException(status_code=502, detail="Tribute не вернул ссылку на оплату")

    return TributeCheckoutOut(
        tribute_product_id=tribute_pid,
        payment_url=web_link or tg_link,
        telegram_deep_link=tg_link or None,
        currency=str(tribute_product.get("currency") or "") or None,
        amount_minor=int(tribute_product.get("amount") or 0) or None,
    )


@router.post("/tribute/webhook")
async def tribute_billing_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not settings.tribute_billing_webhook_enabled:
        raise HTTPException(status_code=503, detail="tribute billing webhook not configured")

    wh_secret = (settings.tribute_billing_webhook_secret or "").strip()
    if wh_secret:
        got = (request.query_params.get("secret") or "").strip()
        if got != wh_secret:
            raise HTTPException(status_code=403, detail="webhook secret")

    raw = await request.body()
    sig_header = request.headers.get("trbt-signature") or request.headers.get("Trbt-Signature")
    api_key = (settings.tribute_billing_api_key or "").strip()
    log.info(
        "tribute billing webhook hit bytes=%s has_signature=%s",
        len(raw),
        bool(sig_header),
    )
    if not verify_tribute_webhook_signature(raw, sig_header, api_key):
        log.warning("tribute billing webhook: invalid signature")
        raise HTTPException(status_code=401, detail="invalid tribute signature")

    try:
        body = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="invalid json body") from e
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="json must be an object")

    try:
        result = await apply_tribute_billing_webhook(session, body=body)
        log.info("tribute billing webhook: %s", result)
        return result
    except Exception:
        log.exception("tribute billing webhook failed")
        raise HTTPException(status_code=500, detail="ingest failed") from None


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
