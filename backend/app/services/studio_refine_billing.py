"""Биллинг refine_prompt: промпт + картинка (+ anchor wardrobe prep при ref/swap)."""

from __future__ import annotations

from typing import Any

from app.services.demo_generations import STUDIO_IMAGE_USAGE_KIND, resolve_image_credit_cost
from app.services.studio_image_pricing import (
    effective_wave_model_for_billing,
    grok_pipeline_for_studio_mode,
)
from app.services.studio_operation_pricing import (
    studio_inpaint_credit_cost,
    studio_prompt_refine_credit_cost,
)

def normalize_studio_mode(raw: str | None) -> str:
    m = (raw or "model_scene").strip().lower().replace("-", "_")
    if m in ("edit", "refine", "enhance"):
        return "photo_edit"
    allowed = frozenset(
        {"model", "model_scene", "photo_edit", "no_face", "face_swap", "grok_compose"}
    )
    if m in allowed:
        return m
    return "model_scene"


def effective_generate_wavespeed(generate_wavespeed: str | None) -> bool:
    return str(generate_wavespeed or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def anchor_pipeline_eligible_from_params(
    params: dict[str, Any],
    *,
    has_scene_image: bool | None = None,
    mask_bytes: bool = False,
) -> bool:
    """Anchor Studio: wardrobe prep + final frame — два WaveSpeed при cache miss."""
    if mask_bytes:
        return False
    if not effective_generate_wavespeed(str(params.get("generate_wavespeed") or "1")):
        return False
    mode = normalize_studio_mode(str(params.get("studio_mode") or ""))
    if mode not in ("face_swap", "model_scene"):
        return False
    mid = str(params.get("model_id") or "").strip()
    if not mid or mid == "0":
        return False
    if has_scene_image is not None:
        return bool(has_scene_image)
    if params.get("image_path") or params.get("image_0_path"):
        return True
    wf_refs = params.get("workflow_refs")
    if isinstance(wf_refs, list) and len(wf_refs) > 0:
        return True
    return False


def refine_prompt_billing_quote(
    plan: str,
    *,
    mask_bytes: bool,
    billing_wave_model: str,
    wan_tier_n: str,
    grok_pipeline: str,
    include_anchor_prep: bool = False,
) -> tuple[str, int, int]:
    """usage_kind, quoted_cost (с промптом), base_studio_credit для demo/reserve."""
    usage_kind = "studio_inpaint" if mask_bytes else STUDIO_IMAGE_USAGE_KIND
    base_studio_credit = (
        studio_inpaint_credit_cost()
        if mask_bytes
        else studio_prompt_refine_credit_cost()
    )
    quoted_cost = resolve_image_credit_cost(
        plan,
        wave_model_id=billing_wave_model,
        wan_edit_tier=wan_tier_n,
        grok_pipeline=grok_pipeline,
        legacy_base=base_studio_credit,
    )
    if not mask_bytes:
        quoted_cost += studio_prompt_refine_credit_cost()
    # Wardrobe prep (dress body) — отдельный WaveSpeed без Grok-compose.
    if include_anchor_prep and not mask_bytes:
        quoted_cost += resolve_image_credit_cost(
            plan,
            wave_model_id=billing_wave_model,
            wan_edit_tier=wan_tier_n,
            grok_pipeline="none",
        )
    return usage_kind, quoted_cost, base_studio_credit


def anchor_prep_credit_cost(
    plan: str,
    *,
    billing_wave_model: str,
    wan_tier_n: str,
) -> int:
    """Стоимость wardrobe prep (один edit без Grok)."""
    return resolve_image_credit_cost(
        plan,
        wave_model_id=billing_wave_model,
        wan_edit_tier=wan_tier_n,
        grok_pipeline="none",
    )


def billing_wave_model_from_params(params: dict[str, Any]) -> str:
    workflow_wave_model = (str(params.get("workflow_wave_model") or "").strip().lower()) or None
    wave_profile_n = (str(params.get("studio_wave_profile") or "nsfw")).strip().lower()
    if wave_profile_n not in ("regular", "nsfw"):
        wave_profile_n = "nsfw"
    return (
        workflow_wave_model
        if workflow_wave_model
        else effective_wave_model_for_billing(None, wave_profile=wave_profile_n)
    )


def grok_pipeline_from_params(params: dict[str, Any]) -> str:
    mode_n = normalize_studio_mode(str(params.get("studio_mode") or "model_scene"))
    workflow_source = params.get("workflow_source")
    return grok_pipeline_for_studio_mode(mode_n, workflow=bool(workflow_source))
