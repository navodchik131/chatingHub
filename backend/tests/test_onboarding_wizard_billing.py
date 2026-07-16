from app.services.demo_generations import (
    model_profile_generation_free,
    onboarding_wizard_profile_free,
    parse_onboarding_wizard_flag,
)


def test_model_profile_free_first_time_any_plan():
    assert model_profile_generation_free(
        plan="standard",
        demo_remaining=0,
        prior_profile_generation=False,
    )
    assert model_profile_generation_free(
        plan="credits",
        demo_remaining=0,
        prior_profile_generation=False,
    )


def test_model_profile_not_free_repeat_without_credits():
    assert not model_profile_generation_free(
        plan="standard",
        demo_remaining=0,
        prior_profile_generation=True,
    )
    assert not model_profile_generation_free(
        plan="credits",
        demo_remaining=0,
        prior_profile_generation=True,
    )


def test_model_profile_free_repeat_credits_with_demo():
    assert model_profile_generation_free(
        plan="credits",
        demo_remaining=3,
        prior_profile_generation=True,
    )


def test_onboarding_wizard_profile_free_credits_with_demo():
    assert onboarding_wizard_profile_free(
        plan="credits",
        demo_remaining=3,
        onboarding_wizard=True,
    )


def test_onboarding_wizard_profile_not_free_without_demo():
    assert not onboarding_wizard_profile_free(
        plan="credits",
        demo_remaining=0,
        onboarding_wizard=True,
    )


def test_onboarding_wizard_profile_not_free_without_flag():
    assert not onboarding_wizard_profile_free(
        plan="credits",
        demo_remaining=3,
        onboarding_wizard=False,
    )


def test_parse_onboarding_wizard_flag():
    assert parse_onboarding_wizard_flag("1")
    assert parse_onboarding_wizard_flag("yes")
    assert not parse_onboarding_wizard_flag(None)
    assert not parse_onboarding_wizard_flag("0")
