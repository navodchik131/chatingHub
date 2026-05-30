"""Nano Banana Pro: префлайт и укорочение промпта."""

from __future__ import annotations

import json

from app.services.studio_prompt_bundle import (
    compact_studio_prompt_for_nano_banana,
    nano_banana_preflight_error,
)


def test_nano_preflight_rejects_nude_pose_on_regular() -> None:
    err = nano_banana_preflight_error(
        wave_profile="regular",
        reference_scene_description="nude full body on sofa, topless",
        image_urls=["https://example.com/a.jpg"],
    )
    assert err is not None
    assert "NSFW" in err or "нагот" in err.lower()


def test_nano_preflight_allows_clothed_regular() -> None:
    err = nano_banana_preflight_error(
        wave_profile="regular",
        reference_scene_description="standing in dress, studio light",
        image_urls=["https://example.com/a.jpg"],
    )
    assert err is None


def test_compact_studio_prompt_strips_realism_engine_when_too_long() -> None:
    huge = {"scene_brief": "x" * 20000, "realism_engine": {"a": 1}, "negative_prompt": "y" * 500}
    raw = "[PREFIX]\n" + json.dumps(huge, ensure_ascii=False)
    out = compact_studio_prompt_for_nano_banana(raw, max_chars=5000)
    assert len(out) <= 5000
    assert "realism_engine" not in out
    assert "scene_brief" in out
