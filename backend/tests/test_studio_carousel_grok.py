from __future__ import annotations

import pytest

from app.services.studio_carousel import (
    build_carousel_grok_wave_prompt,
    carousel_variation_at,
    parse_carousel_grok_prompts,
    static_carousel_variations,
)


def test_parse_carousel_grok_prompts_json() -> None:
    raw = '{"prompts": ["First shot angle", "Second pose", "Third frame"]}'
    out = parse_carousel_grok_prompts(raw, count=3)
    assert out == ["First shot angle", "Second pose", "Third frame"]


def test_parse_carousel_grok_prompts_with_master_read() -> None:
    raw = """{
      "master_read": {
        "camera": "left three-quarter eye-level",
        "pose": "weight on right hip, hand in hair",
        "gaze": "looking at lens",
        "expression": "soft smile",
        "framing": "medium close-up",
        "instagram_opportunity": "add right 3Q and over-shoulder"
      },
      "prompts": ["Right three-quarter, gaze off-camera. Same person as master", "Over-shoulder back view. Partial face must match master", "Closer crop, softer expression. Same person as master"]
    }"""
    out = parse_carousel_grok_prompts(raw, count=3)
    assert len(out) == 3
    assert "Right three-quarter" in out[0]
    assert "Over-shoulder" in out[1]


def test_parse_carousel_grok_prompts_json_with_noise() -> None:
    raw = 'Here you go:\n{"prompts": ["A", "B"]}\nThanks!'
    out = parse_carousel_grok_prompts(raw, count=2)
    assert out == ["A", "B"]

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
    assert "IDENTITY_REINFORCE" in body
    assert "APPLY_SHOT" in body


def test_static_carousel_variations_count() -> None:
    blocks = static_carousel_variations(5)
    assert len(blocks) == 5
    assert all(isinstance(b, str) and b.strip() for b in blocks)


def test_static_carousel_variations_identity_and_variety() -> None:
    blocks = static_carousel_variations(8)
    joined = " ".join(blocks).lower()
    assert "same" in joined and "master" in joined
    assert "right" in joined and "left" in joined
    assert "back" in joined


def test_carousel_variation_order_spreads_sides() -> None:
    first_three = [carousel_variation_at(i).lower() for i in range(3)]
    assert any("right" in s for s in first_three)
    assert any("back" in s for s in first_three)
    assert any("left" in s for s in first_three)
    assert first_three[0] != first_three[1]


def test_load_grok_carousel_compose_system_capture_grammar() -> None:
    from app.services.studio_carousel import load_grok_carousel_compose_system

    system = load_grok_carousel_compose_system()
    low = system.lower()
    assert "capture_type" in low or "capture grammar" in low
    assert "mirror_selfie" in low or "mirror selfie" in low
    assert "phone_selfie" in low or "phone selfie" in low
    assert "environment" in low


def test_parse_carousel_grok_prompts_too_few_raises() -> None:
    with pytest.raises(RuntimeError):
        parse_carousel_grok_prompts('{"prompts": ["only one"]}', count=3)


def test_finalize_carousel_mode_not_photo_edit_prefix() -> None:
    from app.services.studio_openai import (
        finalize_nano_banana_studio_prompt,
        finalize_wavespeed_studio_prompt,
    )

    body = "[SHOT_VARIATION] Camera RIGHT three-quarter."
    wan = finalize_wavespeed_studio_prompt(body, studio_mode="carousel", user_image_first=True)
    nano = finalize_nano_banana_studio_prompt(
        body,
        studio_mode="carousel",
        user_photo_edit_first=False,
        user_pose_reference_is_last=False,
    )
    assert "CAROUSEL_IMG2IMG" in wan
    assert "EDIT_BASE" not in wan
    assert "preserve shot scale" not in wan.lower()
    assert "CAROUSEL_IMG2IMG" in nano
    assert "EDIT_BASE" not in nano


def test_append_carousel_shot_reinforce_first_frame_only() -> None:
    from app.services.studio_carousel import append_carousel_shot_reinforce

    base = "lock + variation"
    assert "FIRST_FRAME_MANDATE" in append_carousel_shot_reinforce(base, shot_index=0)
    assert append_carousel_shot_reinforce(base, shot_index=1) == base
