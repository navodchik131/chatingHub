from app.services.demo_generations import onboarding_wizard_profile_free, parse_onboarding_wizard_flag


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


def test_onboarding_wizard_profile_not_free_standard():
    assert not onboarding_wizard_profile_free(
        plan="standard",
        demo_remaining=3,
        onboarding_wizard=True,
    )


def test_parse_onboarding_wizard_flag():
    assert parse_onboarding_wizard_flag("1")
    assert parse_onboarding_wizard_flag("yes")
    assert not parse_onboarding_wizard_flag(None)
    assert not parse_onboarding_wizard_flag("0")
