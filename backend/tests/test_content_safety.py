"""Tests for studio age gate (minors only — adult NSFW must pass)."""

from __future__ import annotations

import asyncio

import pytest

from app.services.content_safety import (
    MINOR_CONTENT_CODE,
    assert_studio_generation_allowed,
    collect_minor_content_violations,
    find_minor_content_violation,
    minor_content_http_exception,
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


def test_profile_age_under_18_blocked() -> None:
    profile = '{"model_profile": {"age": "16", "name": "Test"}}'
    assert validate_model_profile_text(profile) is not None


def test_profile_age_adult_allowed() -> None:
    profile = '{"model_profile": {"age": "24", "name": "Test"}}'
    assert validate_model_profile_text(profile) is None


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


def test_http_exception_helper() -> None:
    exc = minor_content_http_exception()
    assert exc.status_code == 403
    assert collect_minor_content_violations(texts=["adult 28 yo"], profile_text=None) == []
