"""Детерминированная сборка scene+identity промпта из анализа референса и профиля модели (без Grok freestyle)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.studio_prompt_bundle import (
    _merge_grok_scene_negative,
    _profile_identity_fields,
    grok_figure_anchor_from_profile,
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
) -> str:
    """
    Только сцена: поза, кадр, свет, фон, одежда/coverage.
    Без age/ethnicity/hair/skin/bust — identity идёт отдельным блоком MODEL_IDENTITY.
    """
    pronoun = _pronoun(visibility)
    sentences: list[str] = []

    capture = (analysis.capture_type or "").strip()
    framing = (analysis.framing_crop or "").strip()
    if capture:
        sentences.append(_finish_sentence(capture))
    elif framing:
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

    bg = (analysis.background_summary or "").strip()
    if bg:
        sentences.append(_finish_sentence(bg))

    light = (analysis.lighting_summary or "").strip()
    if light:
        sentences.append(_finish_sentence(light))

    camera = (analysis.camera_summary or "").strip()
    if camera and camera.lower() not in (capture or "").lower():
        sentences.append(_finish_sentence(camera))

    notes = (analysis.scene_notes or "").strip()
    if notes and len(notes) < 400:
        sentences.append(_finish_sentence(notes))

    extra = (user_notes or "").strip()
    if extra:
        sentences.append(_finish_sentence(extra))

    out = " ".join(s for s in sentences if s).strip()
    if not out:
        out = _action_sentence(pronoun, "holds the same pose and framing as the reference crop")
    return out


def build_deterministic_identity_line(
    model_profile_text: str | None,
    visibility: IdentityVisibility,
) -> str:
    """Одна строка identity из профиля — только для видимых регионов."""
    raw = (model_profile_text or "").strip()
    if not raw:
        return grok_figure_anchor_from_profile(None, visibility=visibility)

    try:
        import json

        data = json.loads(raw)
    except json.JSONDecodeError:
        return grok_figure_anchor_from_profile(model_profile_text, visibility=visibility)

    prof: dict | None = None
    if isinstance(data, dict):
        mp = data.get("model_profile")
        prof = mp if isinstance(mp, dict) else data
    fields = _profile_identity_fields(prof if isinstance(prof, dict) else None)

    parts: list[str] = []
    if visibility.include_face and fields.get("face"):
        parts.append(fields["face"])
    if visibility.include_hair and fields.get("hair"):
        parts.append(fields["hair"])
    if visibility.include_body_proportions and fields.get("body_proportions"):
        parts.append(fields["body_proportions"])
    elif visibility.include_body_proportions and fields.get("subject"):
        parts.append(fields["subject"])

    if parts:
        mention = ", ".join(parts)[:680]
        return (
            f"Model identity on visible anatomy: {mention}. "
            "Same person on all visible skin."
        )
    return grok_figure_anchor_from_profile(model_profile_text, visibility=visibility)


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
