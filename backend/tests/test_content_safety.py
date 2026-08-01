"""Tests for studio age gate (minors only — adult NSFW must pass)."""

from __future__ import annotations

import asyncio

import pytest

from app.services.content_safety import (
    MINOR_CONTENT_CODE,
    assert_studio_generation_allowed,
    collect_minor_content_violations,
    extract_profile_age_years,
    find_minor_content_violation,
    minor_content_http_exception,
    profile_declares_adult_age,
    validate_model_profile_text,
)


@pytest.mark.parametrize(
    "text",
    [
        "teen girl in bikini",
        "schoolgirl uniform",
        "15 years old model",
        "underage subject",
        "loli aesthetic",
        "несовершеннолетняя модель",
        "девочка 14 лет",
    ],
)
def test_blocks_minor_prompts(text: str) -> None:
    assert find_minor_content_violation(text) is not None


@pytest.mark.parametrize(
    "text",
    [
        "adult woman 25 years old, nude photoshoot",
        "mature NSFW lingerie, age 30",
        "curvy woman in bedroom, explicit",
        "25 yo glamour model",
    ],
)
def test_allows_adult_nsfw_prompts(text: str) -> None:
    assert find_minor_content_violation(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "adult woman, not a teenager, lingerie photoshoot",
        "must not look like a teen, 28 year old model",
        "no minor, no underage — adult only",
        "avoid schoolgirl aesthetic, mature woman 30 yo",
        "child, minor, underage, teenager, teen, preteen, schoolgirl",
    ],
)
def test_allows_safety_negations_and_blocklists(text: str) -> None:
    assert find_minor_content_violation(text) is None


def test_grok_prose_with_adult_age_allowed() -> None:
    refined = (
        "Model identity: brunette woman, 28, slim build. "
        "She is an adult, not a teenager. Balcony sunset lingerie, phone candid realism."
    )
    assert find_minor_content_violation(refined) is None


def test_profile_age_under_18_blocked() -> None:
    profile = '{"model_profile": {"age": "16", "name": "Test"}}'
    assert validate_model_profile_text(profile) is not None


def test_profile_age_adult_allowed() -> None:
    profile = '{"model_profile": {"age": "24", "name": "Test"}}'
    assert validate_model_profile_text(profile) is None


def test_profile_with_safety_blocklist_and_adult_age_allowed() -> None:
    profile = (
        '{"model_profile": {"age": "28", "name": "Anna", "appearance": "tall brunette woman", '
        '"always_avoid": "child, minor, underage, teenager, teen, preteen, schoolgirl"}}'
    )
    assert validate_model_profile_text(profile) is None
    assert profile_declares_adult_age(profile) is True


def test_profile_age_28_int_allowed() -> None:
    profile = '{"model_profile": {"age": 28, "appearance": "adult woman"}}'
    assert validate_model_profile_text(profile) is None
    assert profile_declares_adult_age(profile) is True


def test_assert_adult_profile_skips_moderation() -> None:
    profile = '{"model_profile": {"age": "28", "always_avoid": "minor, teen, underage"}}'

    async def _run() -> None:
        await assert_studio_generation_allowed(
            description="adult woman 28 years old, lingerie photoshoot",
            profile_text=profile,
            use_moderation=True,
        )

    asyncio.run(_run())


def test_refined_prompt_negative_blocklist_not_scanned() -> None:
    import json

    profile = '{"model_profile": {"age": "28", "appearance": "adult woman"}}'
    refined = json.dumps(
        {
            "positive_prompt": "woman in lingerie on balcony",
            "negative_prompt": (
                "child, minor, underage, teenager, teen, preteen, schoolgirl, schoolboy"
            ),
        }
    )

    async def _run() -> None:
        await assert_studio_generation_allowed(
            description="woman on balcony",
            refined_prompt=refined,
            profile_text=profile,
            use_moderation=True,
        )

    asyncio.run(_run())


def test_assert_raises_with_code() -> None:
    async def _run() -> None:
        await assert_studio_generation_allowed(
            description="teen girl",
            use_moderation=False,
        )

    with pytest.raises(Exception) as exc:
        asyncio.run(_run())
    err = exc.value
    assert getattr(err, "status_code", None) == 403
    detail = getattr(err, "detail", {})
    assert isinstance(detail, dict)
    assert detail.get("code") == MINOR_CONTENT_CODE


def test_assert_adult_profile_skips_grok_refined_scan() -> None:
    profile = '{"model_profile": {"age": "28", "identity_lock_keywords": "adult brunette woman"}}'
    grok_refined = (
        "She is 28 years old, adult woman in lingerie. Not a teenager. "
        "Avoid schoolgirl look. minor skin blemishes on shoulder."
    )

    async def _run() -> None:
        await assert_studio_generation_allowed(
            description="woman on balcony at sunset",
            refined_prompt=grok_refined,
            profile_text=profile,
            use_moderation=True,
        )

    asyncio.run(_run())


def test_age_28_not_matched_as_8_years_old() -> None:
    assert find_minor_content_violation("beautiful woman 28 years old") is None


def test_profile_identity_lock_with_blocklist_words_adult_age() -> None:
    profile = (
        '{"model_profile": {"age": "28", '
        '"identity_lock_keywords": "never teen, no minor, avoid underage look"}}'
    )
    assert validate_model_profile_text(profile) is None


def test_profile_age_early_28s_parsed_as_adult() -> None:
    profile = '{"model_profile": {"age": "early 28s", "name": "Anna"}}'
    assert extract_profile_age_years(profile) == 28
    assert profile_declares_adult_age(profile) is True


def test_profile_age_early_28s_from_identity_lock_keywords() -> None:
    profile = (
        '{"model_profile": {"age": "unknown", '
        '"identity_lock_keywords": "early-28s Caucasian woman"}}'
    )
    assert extract_profile_age_years(profile) == 28
    assert profile_declares_adult_age(profile) is True


def test_assert_early_28s_profile_hat_prompt_allowed() -> None:
    profile = (
        '{"model_profile": {"age": "early 28s", "name": "woman", '
        '"identity_lock_keywords": "early-28s Caucasian woman", '
        '"always_avoid": "teen, minor, underage"}}'
    )
    grok_refined = (
        "Adult woman early 28s wearing a hat on her head, not a teenager, "
        "no minor, avoid schoolgirl look, balcony lingerie candid."
    )

    async def _run() -> None:
        await assert_studio_generation_allowed(
            description="шляпа на голове",
            refined_prompt=grok_refined,
            profile_text=profile,
            use_moderation=True,
        )

    asyncio.run(_run())
