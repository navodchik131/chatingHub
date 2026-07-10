"""Тесты Tribute billing (платформа)."""

from __future__ import annotations

import json

from app.services.tribute_billing_catalog import parse_tribute_billing_catalog


def test_parse_tribute_billing_catalog_nested():
    raw = json.dumps(
        {
            "digital_products": {
                "456": "sub_standard_solo_month",
                "457": {"product": "credits_pack", "credits_quantity": 500},
            },
            "subscriptions": {"12": "sub_standard_pro_month"},
        }
    )
    cat = parse_tribute_billing_catalog(raw)
    assert cat.target_for_digital_product(456).product == "sub_standard_solo_month"
    assert cat.target_for_digital_product(457).credits_quantity == 500
    assert cat.target_for_subscription(12).product == "sub_standard_pro_month"
    assert cat.tribute_product_id_for("sub_standard_solo_month") == 456
    assert cat.tribute_product_id_for("credits_pack", credits_quantity=500) == 457


def test_parse_legacy_flat_map():
    raw = json.dumps({"456": "sub_standard_solo_month"})
    cat = parse_tribute_billing_catalog(raw)
    assert cat.target_for_digital_product(456).product == "sub_standard_solo_month"


def test_tribute_product_id_for_credits_pack_key():
    raw = json.dumps(
        {"digital_products": {"900": {"product": "credits_pack", "credits_quantity": 200}}}
    )
    cat = parse_tribute_billing_catalog(raw)
    assert cat.tribute_product_id_for("credits_pack", credits_quantity=200) == 900
    assert cat.tribute_product_id_for("credits_pack", credits_quantity=100) is None
