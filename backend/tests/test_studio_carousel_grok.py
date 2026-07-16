from __future__ import annotations

import pytest

from app.services.studio_carousel import (
    build_carousel_grok_wave_prompt,
    parse_carousel_grok_prompts,
    static_carousel_variations,
)


def test_parse_carousel_grok_prompts_json() -> None:
    raw = '{"prompts": ["First shot angle", "Second pose", "Third frame"]}'
    out = parse_carousel_grok_prompts(raw, count=3)
    assert out == ["First shot angle", "Second pose", "Third frame"]


def test_parse_carousel_grok_prompts_numbered_lines() -> None:
    raw = """Prompt 1: Low angle full body, weight on left leg.
Prompt 2: Closer portrait, soft gaze to camera.
Prompt 3: Three-quarter from the right."""
    out = parse_carousel_grok_prompts(raw, count=3)
    assert len(out) == 3
    assert "Low angle" in out[0]
    assert "portrait" in out[1]


def test_build_carousel_grok_wave_prompt_includes_lock() -> None:
    body = build_carousel_grok_wave_prompt(
        master_scene_context="Ruby in a kitchen",
        shot_variation="Camera slightly higher, medium shot.",
    )
    assert "CAROUSEL" in body.upper() or "carousel" in body.lower()
    assert "Ruby in a kitchen" in body
    assert "Camera slightly higher" in body


def test_static_carousel_variations_count() -> None:
    blocks = static_carousel_variations(5)
    assert len(blocks) == 5
    assert all(isinstance(b, str) and b.strip() for b in blocks)


def test_static_carousel_variations_gaze_diversity() -> None:
    blocks = static_carousel_variations(8)
    joined = " ".join(blocks).lower()
    assert "profile" in joined or "off-frame" in joined or "off-camera" in joined
    assert "shoulder" in joined or "away" in joined or "down" in joined


def test_parse_carousel_grok_prompts_too_few_raises() -> None:
    with pytest.raises(RuntimeError):
        parse_carousel_grok_prompts('{"prompts": ["only one"]}', count=3)
