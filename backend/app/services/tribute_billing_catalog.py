"""Маппинг цифровых товаров / подписок Tribute → продукты ModelMate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TributeBillingTarget:
    """Внутренний продукт, который выдаём после оплаты в Tribute."""

    product: str
    credits_quantity: int | None = None


@dataclass(frozen=True, slots=True)
class TributeBillingCatalog:
    digital_products: dict[int, TributeBillingTarget]
    subscriptions: dict[int, TributeBillingTarget]

    def target_for_digital_product(self, tribute_product_id: int) -> TributeBillingTarget | None:
        return self.digital_products.get(int(tribute_product_id))

    def target_for_subscription(self, tribute_subscription_id: int) -> TributeBillingTarget | None:
        return self.subscriptions.get(int(tribute_subscription_id))

    def tribute_product_id_for(self, internal_product: str, *, credits_quantity: int | None = None) -> int | None:
        key = (internal_product or "").strip()
        if key == "credits_pack" and credits_quantity is not None:
            key = f"credits_pack:{int(credits_quantity)}"
        for tid, target in self.digital_products.items():
            tkey = target.product
            if target.credits_quantity is not None:
                tkey = f"credits_pack:{target.credits_quantity}"
            if tkey == key:
                return tid
        return None

    def configured(self) -> bool:
        return bool(self.digital_products or self.subscriptions)


def _parse_target(raw: Any) -> TributeBillingTarget | None:
    if isinstance(raw, str) and raw.strip():
        return TributeBillingTarget(product=raw.strip())
    if isinstance(raw, dict):
        product = str(raw.get("product") or "").strip()
        if not product:
            return None
        cq = raw.get("credits_quantity")
        credits_quantity = int(cq) if cq is not None else None
        return TributeBillingTarget(product=product, credits_quantity=credits_quantity)
    return None


def _parse_id_map(section: Any) -> dict[int, TributeBillingTarget]:
    out: dict[int, TributeBillingTarget] = {}
    if not isinstance(section, dict):
        return out
    for key, value in section.items():
        try:
            tid = int(key)
        except (TypeError, ValueError):
            continue
        target = _parse_target(value)
        if target:
            out[tid] = target
    return out


def parse_tribute_billing_catalog(raw_json: str) -> TributeBillingCatalog:
    """
    JSON в .env TRIBUTE_BILLING_PRODUCT_MAP:

    {
      "digital_products": {
        "456": "sub_standard_solo_month",
        "457": {"product": "credits_pack", "credits_quantity": 500}
      },
      "subscriptions": {
        "12": "sub_standard_solo_month"
      }
    }

    Ключи digital_products — ID цифрового товара в Tribute.
  Ключи subscriptions — subscriptionId из Tribute (для renewed_subscription).
    """
    text = (raw_json or "").strip() or "{}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return TributeBillingCatalog(digital_products={}, subscriptions={})

    if not isinstance(data, dict):
        return TributeBillingCatalog(digital_products={}, subscriptions={})

    digital = _parse_id_map(data.get("digital_products"))
    subs = _parse_id_map(data.get("subscriptions"))

    # Плоский legacy-формат { "456": "sub_..." } → только digital_products
    if not digital and not subs:
        digital = _parse_id_map(data)

    return TributeBillingCatalog(digital_products=digital, subscriptions=subs)
