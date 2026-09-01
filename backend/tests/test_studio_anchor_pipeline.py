"""Anchor Studio prompts must match anchor-studio_3.html Mode A/B builders."""

from app.services.studio_anchor_pipeline import (
    REALISM_BLOCK,
    AnchorVisibility,
    anchor_mode_a_scene_first,
    build_mode_a_prompt,
    build_mode_b_prompt,
    detect_bust_portrait_scene,
    detect_face_closeup_scene,
    dressed_body_cache_key,
    filter_anchor_by_visibility,
    hairstyle_style_block,
    identity_marks_block,
    order_mode_a_face_closeup_urls,
    order_mode_a_image_urls,
)
from app.services.studio_openai import finalize_anchor_mode_a_wavespeed_prompt
from app.services.studio_prompt_bundle import extract_creative_notes_from_workflow_description


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
    assert "body proportions reference only" in prompt
    assert "Do NOT copy outfit from this image" in prompt
    assert "Image 3 = target scene" in prompt
    assert "CRITICAL FACE REPLACEMENT" in prompt
    assert "FACE:" in prompt
    assert "NEVER copy marks, tattoos, or scars" in prompt
    assert "OVERLAYS_AND_TEXT" in prompt
    assert "OnlyFans" in prompt
    assert REALISM_BLOCK in prompt
    assert prompt.endswith("extra note")


def test_mode_a_scene_first_reorders_prompt_indices():
    """Seedream: Image1=scene, Image2=face, Image3=body."""
    vis = AnchorVisibility()
    filtered = filter_anchor_by_visibility(SAMPLE_ANCHOR, vis)
    prompt = build_mode_a_prompt(filtered_anchor=filtered, vis=vis, scene_first=True)
    assert "Image 1 = target scene" in prompt
    assert "Image 2 = facial identity reference only" in prompt
    assert "Image 3 = body proportions reference only" in prompt


def test_order_mode_a_image_urls():
    assert order_mode_a_image_urls(
        face_url="f", dressed_url="d", scene_url="s", scene_first=True
    ) == ["s", "f", "d"]
    assert order_mode_a_image_urls(
        face_url="f", dressed_url="d", scene_url="s", scene_first=False
    ) == ["f", "d", "s"]


def test_anchor_mode_a_scene_first_profile():
    assert anchor_mode_a_scene_first(wave_profile="nsfw") is False
    assert anchor_mode_a_scene_first(wave_profile="regular") is False
    assert anchor_mode_a_scene_first(wave_profile="nsfw", wave_model_id="seedream-v5.0-pro") is True
    assert anchor_mode_a_scene_first(wave_profile="nsfw", wave_model_id="wan-2.7") is False


def test_order_mode_a_image_urls_seedream_scene_first():
    assert order_mode_a_image_urls(
        face_url="f", dressed_url="b", scene_url="s", scene_first=True
    ) == ["s", "f", "b"]
    assert order_mode_a_image_urls(
        face_url="f",
        dressed_url="b",
        scene_url="s",
        scene_first=True,
        extra_face_copies=2,
    ) == ["s", "f", "f", "f", "b"]


def test_detect_face_closeup_scene():
    # Чистый headshot — без торса в кадре.
    vis = AnchorVisibility(face=True, hair=True, upper=False, lower=False)
    assert detect_face_closeup_scene(vis, "CAMERA:\n- Shot type: close-up\n")
    # Бюст / до груди — upper visible → полный Mode A с dressed body.
    assert not detect_face_closeup_scene(
        AnchorVisibility(face=True, upper=True, lower=False),
        "CAMERA:\n- Shot type: close-up\n",
    )
    assert not detect_face_closeup_scene(
        AnchorVisibility(face=True, upper=True, lower=True),
        "CAMERA:\n- Shot type: full body\n",
    )


def test_identity_marks_block_upper_body():
    bust = identity_marks_block(AnchorVisibility(face=True, upper=True, lower=False))
    head = identity_marks_block(AnchorVisibility(face=True, upper=False, lower=False))
    assert "NEVER copy marks, tattoos, or scars" in bust
    assert "must NOT keep the sitter's tattoos" in bust
    assert "must NOT keep the sitter's tattoos" not in head


def test_order_mode_a_face_closeup_urls():
    assert order_mode_a_face_closeup_urls(
        face_url="f", scene_url="s", scene_first=True, duplicate_face=True
    ) == ["s", "f", "f"]
    assert order_mode_a_face_closeup_urls(
        face_url="f", scene_url="s", scene_first=False
    ) == ["f", "s"]


def test_order_mode_a_image_urls_extra_face():
    assert order_mode_a_image_urls(
        face_url="f",
        dressed_url="d",
        scene_url="s",
        scene_first=True,
        extra_face_copies=2,
    ) == ["s", "f", "f", "f", "d"]
    assert order_mode_a_image_urls(
        face_url="f",
        dressed_url="d",
        scene_url="s",
        scene_first=False,
        extra_face_copies=2,
    ) == ["f", "f", "f", "d", "s"]


def test_detect_bust_portrait_scene():
    assert detect_bust_portrait_scene(
        AnchorVisibility(face=True, upper=True, lower=False),
        "CAMERA:\n- Shot type: close-up chest-up\n",
    )
    assert detect_bust_portrait_scene(
        AnchorVisibility(face=True, upper=True, lower=False),
        "Pose: finger on lip, playful smile\n",
    )
    # Обычный поясной/полный — не bust.
    assert not detect_bust_portrait_scene(
        AnchorVisibility(face=True, upper=True, lower=False),
        "CAMERA:\n- Shot type: medium waist-up\n",
    )
    assert not detect_bust_portrait_scene(
        AnchorVisibility(face=True, upper=True, lower=True),
        "full body standing\n",
    )
    assert not detect_bust_portrait_scene(
        AnchorVisibility(face=True, upper=False, lower=False),
        "",
    )


def test_mode_a_bust_portrait_order_scene_first_nsfw():
    """Бюст: face×3, dressed body, scene — identity-first."""
    urls = order_mode_a_image_urls(
        face_url="f",
        dressed_url="d",
        scene_url="s",
        scene_first=anchor_mode_a_scene_first(wave_profile="nsfw"),
        extra_face_copies=2,
    )
    assert urls == ["f", "f", "f", "d", "s"]


def test_mode_a_bust_portrait_prompt():
    vis = AnchorVisibility(face=True, upper=True, lower=False)
    filtered = filter_anchor_by_visibility(SAMPLE_ANCHOR, vis)
    prompt = build_mode_a_prompt(
        filtered_anchor=filtered,
        vis=vis,
        bust_portrait=True,
        extra_face_copies=2,
    )
    assert "BUST PORTRAIT FACE SWAP" in prompt
    assert "hand, finger, hair" in prompt
    assert "Images 1–3" in prompt
    assert "Image 4 = body proportions reference only" in prompt
    assert "Image 5 = target scene" in prompt


def test_mode_a_bust_includes_upper_body_marks_block():
    vis = AnchorVisibility(face=True, upper=True, lower=False)
    filtered = filter_anchor_by_visibility(SAMPLE_ANCHOR, vis)
    prompt = build_mode_a_prompt(filtered_anchor=filtered, vis=vis)
    assert "must NOT keep the sitter's tattoos" in prompt
    assert "never the sitter's tattoos" in prompt.lower() or "never" in prompt.lower()


def test_mode_a_hairstyle_lock_from_model_vs_scene():
    vis = AnchorVisibility()
    filtered = filter_anchor_by_visibility(SAMPLE_ANCHOR, vis)
    locked = build_mode_a_prompt(filtered_anchor=filtered, vis=vis, lock_hairstyle_style=True)
    unlocked = build_mode_a_prompt(filtered_anchor=filtered, vis=vis, lock_hairstyle_style=False)
    assert "Hairstyle style, part, texture, and length also come from the model identity" in locked
    assert "Hair color always comes from the model identity" in locked
    assert "Hair color always comes from the model identity" in unlocked
    assert "may follow the scene donor" in unlocked


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
    assert "NEVER copy marks, tattoos, or scars" in prompt
    assert REALISM_BLOCK in prompt


def test_hairstyle_style_block_color_always_from_model():
    locked = hairstyle_style_block(lock_hairstyle_style=True)
    unlocked = hairstyle_style_block(lock_hairstyle_style=False)
    assert "Hair color always comes from the model identity" in locked
    assert "Hair color always comes from the model identity" in unlocked


def test_extract_creative_notes_strips_reference_context():
    raw = (
        "SCENE_DIRECTION:\nKeep playful smile.\n\n"
        "REFERENCE_CONTEXT: Reference 1: scene/pose/camera\n"
        "Do not copy tattoos from ref."
    )
    notes = extract_creative_notes_from_workflow_description(raw)
    assert "REFERENCE_CONTEXT" not in notes
    assert "Keep playful smile" in notes
    assert "Do not copy tattoos from ref" not in notes


def test_extract_creative_notes_strips_reference_context_only_block():
    """Workflow face swap с моделью из кабинета — desc часто только REFERENCE_CONTEXT без SCENE_DIRECTION."""
    raw = (
        "REFERENCE_CONTEXT (each attached workflow image is labeled to match its Role):\n"
        "Reference 1:\n  Role: scene / pose / camera\n"
        "  Notes: Исходная сцена — identity из identity ref."
    )
    notes = extract_creative_notes_from_workflow_description(raw)
    assert notes == ""


def test_finalize_strips_reference_context_from_prompt():
    raw = (
        "Image 3 = target scene.\n\n"
        "REFERENCE_CONTEXT (each attached workflow image is labeled to match its Role):\n"
        "Reference 1:\n  Role: scene / pose / camera"
    )
    out = finalize_anchor_mode_a_wavespeed_prompt(
        raw,
        wave_profile="nsfw",
        lock_model_hairstyle=True,
        scene_first=False,
    )
    assert "REFERENCE_CONTEXT" not in out
    assert "Reference 1:" not in out
    assert "target scene" in out


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


def test_finalize_seedream_scene_first_prefix():
    out = finalize_anchor_mode_a_wavespeed_prompt(
        "Replace face in scene.",
        wave_profile="nsfw",
        lock_model_hairstyle=True,
        scene_first=True,
    )
    assert "[FACE_SWAP — MULTI_REF]" in out
    assert "Image 1" in out and "SOURCE snapshot" in out
    assert "Image 2" in out and "MODEL face" in out
    assert "Image 3" in out and "MODEL body" in out
    assert "[FACE_SWAP — WAN]" not in out


def test_finalize_bust_portrait_nsfw_uses_identity_first_prefix():
    """WAN бюст — identity-first префикс (scene_first=False)."""
    out = finalize_anchor_mode_a_wavespeed_prompt(
        "Replace face in scene.",
        wave_profile="nsfw",
        lock_model_hairstyle=True,
        scene_first=False,
        bust_portrait=True,
    )
    assert "[FACE_SWAP — MULTI_REF]" in out
    assert "Image 1" in out and "MODEL face" in out
    assert "Image 2" in out and "proportions reference only" in out
    assert "Image 3" in out and "SOURCE snapshot" in out
    assert "[MULTI_IMAGE_EDIT — intentional FACE SWAP]" not in out
    assert "[BUST PORTRAIT]" in out
