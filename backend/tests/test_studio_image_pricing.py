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


def test_refine_billing_includes_anchor_prep():
    from app.services.studio_refine_billing import refine_prompt_billing_quote

    _, base, _ = refine_prompt_billing_quote(
        "credits",
        mask_bytes=False,
        billing_wave_model="wan-2.7",
        wan_tier_n="standard",
        grok_pipeline="standard",
        include_anchor_prep=False,
    )
    _, with_prep, _ = refine_prompt_billing_quote(
        "credits",
        mask_bytes=False,
        billing_wave_model="wan-2.7",
        wan_tier_n="standard",
        grok_pipeline="standard",
        include_anchor_prep=True,
    )
    assert with_prep > base


def test_anchor_pipeline_eligible_params():
    from app.services.studio_refine_billing import anchor_pipeline_eligible_from_params

    assert anchor_pipeline_eligible_from_params(
        {"studio_mode": "face_swap", "model_id": "12", "generate_wavespeed": "1"},
        has_scene_image=True,
    )
    assert not anchor_pipeline_eligible_from_params(
        {"studio_mode": "photo_edit", "model_id": "12", "generate_wavespeed": "1"},
        has_scene_image=True,
        mask_bytes=True,
    )
    assert not anchor_pipeline_eligible_from_params(
        {"studio_mode": "model_scene", "model_id": "", "generate_wavespeed": "1"},
        has_scene_image=True,
    )
