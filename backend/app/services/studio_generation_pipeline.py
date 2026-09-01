"""Метки «через что сгенерировано» для архива студии."""

from __future__ import annotations

from typing import Any

from app.db.models import StudioGeneration, StudioJob
from app.services.studio_jobs import job_params

# Человекочитаемые названия AI-движков WaveSpeed.
_WAVE_MODEL_LABELS: dict[str, str] = {
    "nano-banana-2": "Nano Banana",
    "nano-banana-pro": "Nano Banana Pro",
    "gpt-image-2": "GPT Image 2",
    "seedream-v5.0-pro": "Seedream 5 Pro",
    "wan-2.7": "Wan 2.7",
    "wan-2.7-pro": "Wan 2.7 Pro",
}

_SEEDANCE_VARIANT_LABELS: dict[str, str] = {
    "standard": "Seedance 1.5",
    "seedance_25": "Seedance 2.5",
    "mini": "Seedance Mini",
}


def _truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in ("1", "true", "yes", "on")


def _wave_engine_label(params: dict[str, Any]) -> str | None:
    wave = (
        str(params.get("workflow_wave_model") or params.get("wave_model_id") or "").strip().lower()
    )
    if not wave:
        profile = str(params.get("studio_wave_profile") or "").strip().lower()
        if profile == "regular":
            return "Nano Banana Pro"
        if profile == "nsfw":
            tier = str(params.get("wan_edit_tier") or "standard").strip().lower()
            if tier == "pro":
                return "Wan 2.7 Pro"
            return "Seedream 5 Pro"
        return None
    label = _WAVE_MODEL_LABELS.get(wave)
    if label:
        tier = str(params.get("wan_edit_tier") or "standard").strip().lower()
        if wave == "wan-2.7" and tier == "pro":
            return "Wan 2.7 Pro"
        return label
    return wave.replace("-", " ").title()


def _seedance_engine_label(params: dict[str, Any], *, video_backend: str) -> str:
    if (video_backend or "").strip().lower() == "evolink":
        variant = str(params.get("seedance_variant") or "standard").strip().lower()
        return _SEEDANCE_VARIANT_LABELS.get(variant, "Seedance Sale")
    variant = str(params.get("seedance_variant") or "standard").strip().lower()
    return _SEEDANCE_VARIANT_LABELS.get(variant, "Seedance 1.5")


def _image_mode_key(params: dict[str, Any]) -> str:
    mode = str(params.get("studio_mode") or "model_scene").strip().lower().replace("-", "_")
    if mode == "photo_edit":
        return "image_photo_edit"
    if mode == "face_swap":
        return "image_face_swap"
    if mode == "no_face":
        return "image_no_face"
    if mode == "grok_compose":
        return "image_grok_compose"
    if mode == "model":
        return "image_model"
    if params.get("workflow_source"):
        return "image_workflow"
    return "image_model_scene"


def resolve_generation_pipeline(
    row: StudioGeneration,
    job: StudioJob | None = None,
) -> tuple[str | None, str | None]:
    """Возвращает (pipeline_key, engine_label) для карточки архива."""
    params: dict[str, Any] = job_params(job) if job else {}
    job_type = (job.job_type or "").strip() if job else ""
    vb = (getattr(row, "video_backend", None) or "wavespeed").strip().lower()

    if row.carousel_shot_index is not None:
        return "image_carousel_shot", _wave_engine_label(params)

    if job_type == "carousel":
        return "image_carousel", _wave_engine_label(params)

    if job_type == "upscale":
        return "image_upscale", _wave_engine_label(params) or "Upscale"

    if job_type in ("shot_batch_render", "shot_batch_wizard"):
        return "image_shot_batch", _wave_engine_label(params) or "Shot batch"

    if job_type == "seedance_director_generate":
        return "video_seedance_director", _seedance_engine_label(params, video_backend=vb)

    if job_type.startswith("model_bootstrap"):
        return "image_bootstrap", _wave_engine_label(params)

    if job_type == "motion_render_video":
        mc_wizard = _truthy(str(params.get("motion_control_wizard") or ""))
        use_outline = _truthy(str(params.get("use_motion_outline") or ""))
        vp = str(params.get("video_provider") or "seedance_t2v").strip().lower()
        mv_id = str(params.get("motion_video_file_id") or "").strip()
        prompt_only = _truthy(str(params.get("prompt_only_mode") or ""))

        if mc_wizard:
            key = "video_motion_control_outline" if use_outline else "video_motion_control"
            return key, _seedance_engine_label(params, video_backend=vb)

        if vp == "grok_imagine_i2v":
            return "video_grok", "Grok Imagine"

        if prompt_only or vp == "seedance_i2v":
            return "video_prompt", _seedance_engine_label(params, video_backend=vb)

        if mv_id:
            if _truthy(str(params.get("use_motion_outline") or "")):
                outline = True
            elif mc_wizard:
                outline = False
            else:
                from app.config import settings

                outline = bool(settings.motion_outline_enabled)
            key = "video_motion_swap_outline" if outline else "video_motion_swap"
            return key, _seedance_engine_label(params, video_backend=vb)

        return "video_prompt", _seedance_engine_label(params, video_backend=vb)

    if job_type == "refine_prompt":
        return _image_mode_key(params), _wave_engine_label(params)

    # Эвристики без job (старые записи).
    if (row.content_type or "").startswith("video/"):
        if vb == "evolink":
            return "video_seedance_sale", "Seedance Sale"
        if row.motion_video_prompt_auto:
            return "video_motion_swap", _seedance_engine_label(params, video_backend=vb)
        return "video_prompt", _seedance_engine_label(params, video_backend=vb)

    if row.outfit_generation_id:
        return "image_outfit", _wave_engine_label(params)

    return "image_model_scene", _wave_engine_label(params)
