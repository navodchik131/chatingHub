from app.services.billing_plan import (
    is_credits_plan,
    is_pro_plan,
    normalize_billing_plan,
    platform_covers_studio_api_costs,
    studio_charges_credits,
)
from app.services.studio_image_pricing import quote_studio_image_credits


def test_normalize_billing_plan_legacy():
    assert normalize_billing_plan("managed") == "standard"
    assert normalize_billing_plan("byok") == "pro"
    assert normalize_billing_plan("credits") == "credits"


def test_pro_does_not_charge_credits():
    assert studio_charges_credits("pro") is False
    assert platform_covers_studio_api_costs("credits") is True
    assert is_credits_plan("credits") is True
    assert is_pro_plan("pro") is True


def test_quote_wan_pro_costs_more():
    std = quote_studio_image_credits(
        wave_model_id="wan-2.7", wan_edit_tier="standard", grok_pipeline="standard"
    )
    pro = quote_studio_image_credits(
        wave_model_id="wan-2.7", wan_edit_tier="pro", grok_pipeline="standard"
    )
    assert pro > std


def test_nano_banana_2_cheaper_than_pro_model():
    nb2 = quote_studio_image_credits(
        wave_model_id="nano-banana-2", grok_pipeline="light"
    )
    nbp = quote_studio_image_credits(
        wave_model_id="nano-banana-pro", grok_pipeline="light"
    )
    assert nb2 <= nbp
