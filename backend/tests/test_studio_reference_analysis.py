"""Тесты анализа референса и visibility-плана."""

from __future__ import annotations

import json

from app.services.studio_reference_analysis import (
    ReferenceAnalysis,
    build_grok_identity_instruction,
    build_identity_visibility,
    build_prompt_region_policy_block,
    build_studio_prompt_plan,
    filter_identity_reference_dict,
    filter_model_images_for_visibility,
    format_reference_scene_from_analysis,
    parse_reference_analysis_json,
    prompt_regions_to_omit,
    prune_skeleton_for_visibility,
    sanitize_wavespeed_prose_for_visibility,
    visibility_pose_prefix_kind,
)


def test_parse_reference_analysis_json():
    raw = json.dumps(
        {
            "face_in_frame": False,
            "hair_in_frame": False,
            "visible_regions": ["LEGS", "FEET"],
            "framing_crop": "lower legs only, head cropped out",
        }
    )
    a = parse_reference_analysis_json(raw)
    assert a is not None
    assert a.face_in_frame is False
    assert "LEGS" in a.normalized_regions()


def test_visibility_headless_crop():
    analysis = ReferenceAnalysis(
        face_in_frame=False,
        hair_in_frame=False,
        visible_regions=["LEGS", "FEET"],
        framing_crop="mid-thigh to feet",
    )
    vis = build_identity_visibility(analysis)
    assert vis.headless_crop is True
    assert vis.head_in_reference is False
    assert vis.include_face is False
    assert vis.include_hair is False
    assert "face" not in vis.allowed_image_kinds
    assert "turnaround" in vis.allowed_image_kinds


def test_visibility_head_partial_back_view():
    analysis = ReferenceAnalysis(
        face_in_frame=False,
        head_partial=True,
        hair_in_frame=True,
        visible_regions=["BUTT", "LEGS", "HAIR"],
        framing_crop="rear view, back of head visible, face not visible",
    )
    vis = build_identity_visibility(analysis)
    assert vis.headless_crop is False
    assert vis.head_in_reference is True
    assert vis.include_face is False
    assert "face" not in vis.allowed_image_kinds
    assert "turnaround" in vis.allowed_image_kinds
    assert visibility_pose_prefix_kind(vis) == "face_hidden"


def test_prune_skeleton_removes_face_fields():
    skeleton = json.dumps(
        {
            "subject": {
                "identity": {
                    "face_features": "<FROM_MODEL_PROFILE>",
                    "hair": {"color": "brown"},
                    "body_type": "<FROM_MODEL_PROFILE>",
                },
                "expression": {"eyes": "<FILL>"},
                "hair_in_scene": {"style_now": "<FILL>"},
            }
        }
    )
    vis = build_identity_visibility(
        ReferenceAnalysis(face_in_frame=False, visible_regions=["LEGS"])
    )
    pruned = json.loads(prune_skeleton_for_visibility(skeleton, vis))
    ident = pruned["subject"]["identity"]
    assert "face_features" not in ident
    assert "hair" not in ident
    assert "expression" not in pruned["subject"]
    assert "hair_in_scene" not in pruned["subject"]


def test_filter_compact_identity():
    vis = build_identity_visibility(
        ReferenceAnalysis(face_in_frame=False, visible_regions=["FEET"])
    )
    out = filter_identity_reference_dict(
        {
            "subject": "24yo",
            "face": "green eyes",
            "hair": "long brown",
            "body_proportions": "curvy",
        },
        vis,
    )
    assert "face" not in out
    assert "hair" not in out
    assert out.get("body_proportions")


def test_build_prompt_plan_keeps_requested_mode():
    analysis = ReferenceAnalysis(
        face_in_frame=False,
        visible_regions=["LEGS", "FEET"],
        framing_crop="legs only",
        scene_notes="FRAMING: legs only",
    )
    plan = build_studio_prompt_plan(
        analysis=analysis,
        skeleton='{"subject": {"identity": {"face_features": "x"}}}',
        model_profile_text='{"face_features": "pretty"}',
        requested_studio_mode="model_scene",
    )
    assert plan.effective_studio_mode == "model_scene"
    assert plan.skip_no_face_suffix is True
    assert "FACE_IN_FRAME: false" in plan.reference_scene_description


def test_build_prompt_plan_head_partial_keeps_mode():
    analysis = ReferenceAnalysis(
        face_in_frame=False,
        head_partial=True,
        hair_in_frame=True,
        visible_regions=["BUTT", "TORSO"],
        framing_crop="rear view on bed",
    )
    plan = build_studio_prompt_plan(
        analysis=analysis,
        skeleton='{"subject": {}}',
        model_profile_text=None,
        requested_studio_mode="model_scene",
    )
    assert plan.effective_studio_mode == "model_scene"
    assert plan.skip_no_face_suffix is False
    assert "back/side of head" in plan.reference_scene_description


def test_grok_instruction_no_face_when_head_partial():
    vis = build_identity_visibility(
        ReferenceAnalysis(
            face_in_frame=False,
            head_partial=True,
            hair_in_frame=True,
            visible_regions=["BUTT"],
        )
    )
    text = build_grok_identity_instruction(vis)
    assert "PROMPT_MENTION" in text or "PROMPT_OMIT" in build_prompt_region_policy_block(vis)
    assert "Match face" not in text
    assert "end ---" not in text.lower()


def test_prompt_region_policy_rear_view():
    vis = build_identity_visibility(
        ReferenceAnalysis(
            face_in_frame=False,
            head_partial=True,
            hair_in_frame=True,
            visible_regions=["BUTT", "TORSO", "HAIR", "ARMS"],
        )
    )
    block = build_prompt_region_policy_block(vis)
    assert "PROMPT_MENTION" in block
    assert "face" in block.lower()
    assert "PROMPT_OMIT" in block
    omit = prompt_regions_to_omit(vis)
    assert any("face" in x for x in omit)


def test_sanitize_drops_face_and_meta_when_headless():
    vis = build_identity_visibility(
        ReferenceAnalysis(
            face_in_frame=False,
            head_partial=True,
            hair_in_frame=True,
            visible_regions=["BUTT", "TORSO", "HAIR"],
        )
    )
    raw = (
        "A blonde model on all fours on white bedding, rear view, soft daylight. "
        "She has a playful smile and green eyes. "
        "Match face and hair from the face reference photo. "
        "Long lean legs crossed at the ankles."
    )
    out = sanitize_wavespeed_prose_for_visibility(raw, vis)
    low = out.lower()
    assert "match face" not in low
    assert "green eyes" not in low
    assert "smile" not in low
    assert "legs" not in low
    assert "all fours" in low or "bedding" in low


def test_format_reference_scene():
    text = format_reference_scene_from_analysis(
        ReferenceAnalysis(
            face_in_frame=True,
            hair_in_frame=True,
            framing_crop="face and shoulders",
            pose_summary="looking at camera",
        )
    )
    assert "FRAMING:" in text
    assert "POSE:" in text


def test_filter_model_images_no_face():
    from types import SimpleNamespace

    imgs = [
        SimpleNamespace(id=1, image_kind="face"),
        SimpleNamespace(id=2, image_kind="body"),
        SimpleNamespace(id=3, image_kind="turnaround"),
    ]
    vis = build_identity_visibility(
        ReferenceAnalysis(face_in_frame=False, visible_regions=["LEGS"])
    )
    filtered = filter_model_images_for_visibility(imgs, vis)  # type: ignore[arg-type]
    kinds = {im.image_kind for im in filtered}
    assert "face" not in kinds
    assert "body" in kinds
    assert "turnaround" in kinds
