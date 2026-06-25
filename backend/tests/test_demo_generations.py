import pytest
from fastapi import HTTPException

from app.services.demo_generations import (
    assert_demo_only_user_model_allowed,
    demo_request_eligible_for_free_slot,
)
from app.services.studio_image_pricing import demo_allowed_wave_model_id


def test_demo_nano_regular_light():
    nb = demo_allowed_wave_model_id()
    assert demo_request_eligible_for_free_slot(
        wave_model_id=nb,
        grok_pipeline="light",
        wave_profile="regular",
    )
    assert not demo_request_eligible_for_free_slot(
        wave_model_id=nb,
        grok_pipeline="standard",
        wave_profile="regular",
    )


def test_demo_wan_nsfw_standard():
    assert demo_request_eligible_for_free_slot(
        wave_model_id=None,
        grok_pipeline="standard",
        wave_profile="nsfw",
    )
    assert demo_request_eligible_for_free_slot(
        wave_model_id="wan-2.7",
        grok_pipeline="standard",
        wave_profile="nsfw",
    )
    assert not demo_request_eligible_for_free_slot(
        wave_model_id="wan-2.7",
        grok_pipeline="standard",
        wave_profile="regular",
    )
    assert not demo_request_eligible_for_free_slot(
        wave_model_id="wan-2.7",
        grok_pipeline="standard",
        wave_profile="nsfw",
        wan_edit_tier="pro",
    )


def test_assert_demo_only_blocks_premium_without_credits():
    nb = demo_allowed_wave_model_id()
    assert_demo_only_user_model_allowed(
        plan="credits",
        demo_remaining=2,
        credits_balance=0,
        wave_model_id=nb,
        grok_pipeline="light",
        wave_profile="regular",
    )
    assert_demo_only_user_model_allowed(
        plan="credits",
        demo_remaining=2,
        credits_balance=0,
        wave_model_id=None,
        grok_pipeline="standard",
        wave_profile="nsfw",
    )
    with pytest.raises(HTTPException) as exc:
        assert_demo_only_user_model_allowed(
            plan="credits",
            demo_remaining=2,
            credits_balance=0,
            wave_model_id="nano-banana-pro",
            grok_pipeline="light",
            wave_profile="regular",
        )
    assert exc.value.status_code == 402
    assert "wan-2.7" in str(exc.value.detail)


def test_assert_demo_skipped_when_credits_available():
    assert_demo_only_user_model_allowed(
        plan="credits",
        demo_remaining=2,
        credits_balance=50,
        wave_model_id="nano-banana-pro",
        grok_pipeline="standard",
        wave_profile="nsfw",
    )
