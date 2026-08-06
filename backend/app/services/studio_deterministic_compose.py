"""Детерминированная сборка scene+identity промпта из анализа референса и профиля модели (без Grok freestyle)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.studio_prompt_bundle import (
    _merge_grok_scene_negative,
    extract_creative_notes_from_workflow_description,
    reference_scene_text_for_prompt,
    strip_donor_identity_from_scene_prose,
    strip_soft_dof_from_scene_prose,
)
from app.services.studio_reference_analysis import (
    IdentityVisibility,
    ReferenceAnalysis,
    StudioPromptPlan,
    format_reference_scene_from_analysis,
)


@dataclass(frozen=True)
class DeterministicComposeResult:
    wavespeed_scene_prompt: str
    reference_scene_lock: str
    negative_prompt: str


def _pronoun(visibility: IdentityVisibility) -> str:
    if visibility.headless_crop:
        return "The visible body"
    return "She"


def _finish_sentence(clause: str) -> str:
    c = (clause or "").strip().rstrip(".")
    return f"{c}." if c else ""


_SKIP_REFERENCE_LINE_PREFIXES = (
    "FACE_IN_FRAME:",
    "HAIR_IN_FRAME:",
    "VISIBLE_REGIONS:",
)


def reference_analysis_text_to_scene_prose(text: str) -> str:
    """Превращает блок REFERENCE_ANALYSIS (POSE:/FRAMING:/…) в связный prose для WaveSpeed."""
    parts: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(line.startswith(p) for p in _SKIP_REFERENCE_LINE_PREFIXES):
            continue
        if ":" in line:
            _label, _, body = line.partition(":")
            body = body.strip()
            if not body or body.startswith("(unspecified"):
                continue
            parts.append(body.rstrip(".") + ".")
        else:
            parts.append(line.rstrip(".") + ".")
    joined = " ".join(parts).strip()
    return strip_soft_dof_from_scene_prose(strip_donor_identity_from_scene_prose(joined))


def _action_sentence(pronoun: str, clause: str) -> str:
    c = (clause or "").strip().rstrip(".")
    if not c:
        return ""
    low = c.lower()
    if low.startswith(
        ("she ", "he ", "they ", "the ", "visible ", "a ", "an ", "her ", "his ")
    ):
        return _finish_sentence(c)
    if pronoun.lower().startswith("the "):
        return _finish_sentence(f"{pronoun} shows {c[0].lower()}{c[1:]}")
    return _finish_sentence(f"{pronoun} {c[0].lower()}{c[1:]}")


def build_deterministic_scene_prose(
    analysis: ReferenceAnalysis,
    *,
    visibility: IdentityVisibility,
    user_notes: str | None = None,
    reference_scene_description: str | None = None,
) -> str:
    """
    Только сцена: поза, кадр, свет, фон, одежда/coverage.
    Без age/ethnicity/hair/skin/bust — identity идёт отдельным блоком MODEL_IDENTITY.
    """
    notes = strip_soft_dof_from_scene_prose((analysis.scene_notes or "").strip())
    ref_full = reference_scene_text_for_prompt(reference_scene_description)
    if notes and len(notes) >= 280:
        out = strip_donor_identity_from_scene_prose(notes)
    elif ref_full:
        out = reference_analysis_text_to_scene_prose(ref_full)
    else:
        pronoun = _pronoun(visibility)
        sentences: list[str] = []

        capture = (analysis.capture_type or "").strip()
        framing = (analysis.framing_crop or "").strip()
        if capture:
            sentences.append(_finish_sentence(capture))
        if framing and framing.lower() not in (capture or "").lower():
            sentences.append(_finish_sentence(framing))

        pose = (analysis.pose_summary or "").strip()
        if pose:
            sentences.append(_action_sentence(pronoun, pose))

        clothing = (analysis.clothing_summary or analysis.wardrobe_coverage or "").strip()
        if clothing:
            low = clothing.lower()
            if low.startswith(("she ", "wearing", "nude", "topless", "bottomless", "no ")):
                sentences.append(_finish_sentence(clothing))
            elif "nude" in low or "topless" in low or "no clothing" in low:
                sentences.append(_finish_sentence(clothing))
            else:
                sentences.append(_action_sentence(pronoun, f"wears {clothing}"))

        scale = (analysis.subject_scale_in_frame or "").strip()
        if scale:
            sentences.append(_finish_sentence(scale))

        bg = (analysis.background_summary or "").strip()
        if bg:
            sentences.append(_finish_sentence(strip_soft_dof_from_scene_prose(bg)))

        depth = (analysis.background_depth or "").strip()
        if depth and depth.lower() not in (bg or "").lower():
            sentences.append(_finish_sentence(depth))

        ground = (analysis.ground_plane_notes or "").strip()
        if ground:
            sentences.append(_finish_sentence(ground))

        perspective = (analysis.perspective_vanishing or "").strip()
        if perspective:
            sentences.append(_finish_sentence(perspective))

        light = (analysis.lighting_summary or "").strip()
        if light:
            sentences.append(_finish_sentence(light))

        camera = (analysis.camera_summary or "").strip()
        if camera and camera.lower() not in (capture or "").lower():
            sentences.append(_finish_sentence(strip_soft_dof_from_scene_prose(camera)))

        if notes:
            sentences.append(_finish_sentence(notes))

        out = " ".join(s for s in sentences if s).strip()
        if not out:
            out = _action_sentence(pronoun, "holds the same pose and framing as the reference crop")

    extra = extract_creative_notes_from_workflow_description(user_notes)
    if extra and extra.lower() not in out.lower():
        out = f"{out.rstrip('.')}. {extra.rstrip('.')}.".strip()

    return strip_soft_dof_from_scene_prose(out)


def build_deterministic_identity_line(
    model_profile_text: str | None,
    visibility: IdentityVisibility,
) -> str:
    """Короткая identity-строка — visibility-aware, generation_packs или legacy fallback."""
    from app.services.studio_character_profile import build_identity_line_from_profile

    return build_identity_line_from_profile(model_profile_text, visibility)


def compose_studio_scene_deterministic(
    *,
    prompt_plan: StudioPromptPlan,
    model_profile_text: str | None,
    user_notes: str | None = None,
) -> DeterministicComposeResult:
    """Собирает scene prose + lock/negative без вызова Grok compose."""
    visibility = prompt_plan.visibility
    analysis = prompt_plan.analysis
    scene = build_deterministic_scene_prose(
        analysis,
        visibility=visibility,
        user_notes=user_notes,
        reference_scene_description=prompt_plan.reference_scene_description,
    )
    lock = format_reference_scene_from_analysis(analysis)
    negative = _merge_grok_scene_negative(
        model_profile_text=model_profile_text,
        extra_negative=None,
        reference_scene_description=prompt_plan.reference_scene_description,
    )
    return DeterministicComposeResult(
        wavespeed_scene_prompt=scene,
        reference_scene_lock=lock[:400] if lock else "",
        negative_prompt=negative,
    )
