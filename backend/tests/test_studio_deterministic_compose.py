"""Детерминированная сборка промпта: analysis + model profile."""

from app.services.studio_deterministic_compose import (
    build_deterministic_scene_prose,
    compose_studio_scene_deterministic,
)
from app.services.studio_openai import finalize_wavespeed_studio_prompt
from app.services.studio_prompt_bundle import prepare_positive_prompt_json
from app.services.studio_reference_analysis import (
    IdentityVisibility,
    ReferenceAnalysis,
    StudioPromptPlan,
    build_identity_visibility,
    build_studio_prompt_plan,
)


def _analysis_mirror_selfie() -> ReferenceAnalysis:
    return ReferenceAnalysis(
        face_in_frame=True,
        hair_in_frame=True,
        visible_regions=["FACE", "CHEST", "TORSO", "ARMS", "FULL_BODY"],
        framing_crop="Full-body mirror selfie, subject centered",
        pose_summary="stands in front of a large mirror holding a smartphone at chest height",
        clothing_summary="wearing only a tight white mini skirt and black sheer thigh-high stockings",
        background_summary="Luxury hotel room with dark furniture and city skyline through windows",
        lighting_summary="Soft indoor light mixed with city glow on reflective surfaces",
        camera_summary="Mirror reflection, phone at chest height",
        capture_type="mirror selfie at night",
        wardrobe_coverage="topless with mini skirt and stockings",
    )


def test_deterministic_scene_prose_has_no_donor_identity_opener():
    vis = build_identity_visibility(_analysis_mirror_selfie(), wave_profile="nsfw")
    prose = build_deterministic_scene_prose(_analysis_mirror_selfie(), visibility=vis)
    low = prose.lower()
    assert "mirror selfie" in low or "mirror" in low
    assert "white mini skirt" in low
    assert "23-year-old" not in low
    assert "eurasian" not in low


def test_compose_studio_scene_deterministic_from_plan():
    analysis = _analysis_mirror_selfie()
    vis = build_identity_visibility(analysis, wave_profile="nsfw")
    plan = StudioPromptPlan(
        analysis=analysis,
        visibility=vis,
        reference_scene_description="POSE: mirror selfie",
        pruned_skeleton="{}",
        filtered_model_profile_text='{"model_profile":{"body_type":"hourglass, full bust"}}',
        effective_studio_mode="model_scene",
        skip_no_face_suffix=False,
    )
    out = compose_studio_scene_deterministic(
        prompt_plan=plan,
        model_profile_text=plan.filtered_model_profile_text,
    )
    assert "mirror" in out.wavespeed_scene_prompt.lower()
    assert "23-year-old" not in out.wavespeed_scene_prompt.lower()
    assert out.reference_scene_lock
    assert "donor" not in out.negative_prompt.lower()
    assert "reference sitter" not in out.negative_prompt.lower()


def test_deterministic_compose_wavespeed_pipeline():
    analysis = _analysis_mirror_selfie()
    vis = build_identity_visibility(analysis, wave_profile="nsfw")
    scene = build_deterministic_scene_prose(analysis, visibility=vis)
    profile = '{"model_profile":{"body_type":"curvy hourglass, full bust, narrow waist","face_features":"brown eyes, soft lips"}}'

    positive, neg = prepare_positive_prompt_json(
        scene,
        brief_mode="deterministic_compose",
        model_profile_text=profile,
        wavespeed_identity_legend="Image 2: body proportions; Image 3: face likeness",
        visibility=vis,
        include_realism_engine=False,
    )
    assert "MODEL_IDENTITY" not in positive
    assert "Model identity" in positive or "model identity" in positive.lower()
    assert "hourglass" in positive.lower() or "curvy" in positive.lower()
    assert "23-year-old" not in positive.lower()
    assert "Attached model reference photos" in positive

    ws = finalize_wavespeed_studio_prompt(
        positive,
        studio_mode="model_scene",
        user_image_first=False,
        prompt_brief_mode="deterministic_compose",
    )
    assert "MODEL_SCENE" in ws or "identity" in ws.lower()
    assert "[NEGATIVE_PROMPT]" not in ws

    from app.services.studio_prompt_bundle import append_negative_to_wavespeed_prompt

    full = append_negative_to_wavespeed_prompt(ws, neg, brief_mode="deterministic_compose")
    assert "[NEGATIVE_PROMPT]" not in full
    assert full == ws.rstrip()


def test_build_studio_prompt_plan_enables_deterministic_path():
    skeleton = '{"subject":{}}'
    plan = build_studio_prompt_plan(
        analysis=_analysis_mirror_selfie(),
        skeleton=skeleton,
        model_profile_text='{"model_profile":{"body_type":"athletic"}}',
        requested_studio_mode="model_scene",
        wave_profile="nsfw",
    )
    assert plan.visibility.include_face is True
    assert "POSE:" in plan.reference_scene_description


def test_grok_figure_anchor_truncates_on_word_boundary():
    from app.services.studio_prompt_bundle import grok_figure_anchor_from_profile

    long_body = " ".join(["wide rounded hips with natural curve"] * 40)
    profile = f'{{"model_profile": {{"body_proportions": "{long_body}"}}}}'
    anchor = grok_figure_anchor_from_profile(profile)
    assert "wide rounde —" not in anchor
    assert anchor.endswith("…") or len(anchor) < 900
    assert "FIGURE_LOCK" not in anchor or "Model body" in anchor


def test_build_studio_prompt_plan_works_with_empty_skeleton():
    plan = build_studio_prompt_plan(
        analysis=_analysis_mirror_selfie(),
        skeleton="",
        model_profile_text='{"model_profile":{"body_type":"athletic"}}',
        requested_studio_mode="model_scene",
        wave_profile="nsfw",
    )
    assert plan.reference_scene_description
    assert plan.visibility.include_body_proportions
