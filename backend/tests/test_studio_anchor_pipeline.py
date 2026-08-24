"""Anchor Studio prompts must match anchor-studio_3.html Mode A/B builders."""

from app.services.studio_anchor_pipeline import (
    REALISM_BLOCK,
    AnchorVisibility,
    build_mode_a_prompt,
    build_mode_b_prompt,
    dressed_body_cache_key,
    filter_anchor_by_visibility,
)


SAMPLE_ANCHOR = """FACE:
- Face shape: oval
- Eyes: green

HAIR:
- Color: blonde
- Length: shoulder

UPPER BODY:
- Bust: average

LOWER BODY:
- Hips: average

GENERAL BUILD:
- Overall build: slim
"""


def test_mode_a_prompt_matches_html_contract():
    vis = AnchorVisibility(face=True, hair=True, upper=True, lower=True)
    filtered = filter_anchor_by_visibility(SAMPLE_ANCHOR, vis)
    prompt = build_mode_a_prompt(filtered_anchor=filtered, vis=vis, notes="extra note")
    assert "Image 1 = facial identity reference only" in prompt
    assert "Image 2 = body proportions and outfit reference" in prompt
    assert "Image 3 = target scene" in prompt
    assert "FACE:" in prompt
    assert REALISM_BLOCK in prompt
    assert prompt.endswith("extra note")


def test_mode_b_prompt_has_scene_text_not_image3():
    vis = AnchorVisibility(face=True, hair=False, upper=True, lower=False)
    filtered = filter_anchor_by_visibility(SAMPLE_ANCHOR, vis)
    prompt = build_mode_b_prompt(
        filtered_anchor=filtered,
        scene_description="ENVIRONMENT:\n- Location/setting: beach\n",
        vis=vis,
    )
    assert "Image 1 = facial identity reference." in prompt
    assert "Image 2 = body and outfit reference." in prompt
    assert "Image 3" not in prompt
    assert "ENVIRONMENT:" in prompt
    assert "HAIR:" not in filtered
    assert "LOWER BODY:" not in filtered
    assert "not clearly visible" in prompt or "Hair is not clearly visible" in prompt
    assert REALISM_BLOCK in prompt


def test_dressed_body_cache_key_stable():
    vis = AnchorVisibility()
    a = dressed_body_cache_key(
        model_id=1,
        face_image_id=10,
        body_image_id=20,
        scene_bytes=b"abc",
        vis=vis,
    )
    b = dressed_body_cache_key(
        model_id=1,
        face_image_id=10,
        body_image_id=20,
        scene_bytes=b"abc",
        vis=vis,
    )
    c = dressed_body_cache_key(
        model_id=1,
        face_image_id=10,
        body_image_id=20,
        scene_bytes=b"abd",
        vis=vis,
    )
    assert a == b
    assert a != c
