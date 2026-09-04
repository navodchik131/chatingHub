"""Метки pipeline/engine для карточек архива."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.studio_generation_pipeline import resolve_generation_pipeline


def _job(job_type: str, params: dict):
    return SimpleNamespace(job_type=job_type, params_json=json.dumps(params))


def test_motion_control_wavespeed_shows_seedance_20_not_15():
    row = SimpleNamespace(
        carousel_shot_index=None,
        content_type="video/mp4",
        motion_video_prompt_auto=False,
        outfit_generation_id=None,
        video_backend="wavespeed",
    )
    job = _job(
        "motion_render_video",
        {
            "motion_control_wizard": "1",
            "seedance_variant": "standard",
            "video_provider": "seedance_t2v",
        },
    )
    key, engine = resolve_generation_pipeline(row, job)
    assert key == "video_motion_control"
    assert engine == "Seedance 2.0"
    assert "1.5" not in (engine or "")


def test_motion_control_evolink_shows_seedance_sale():
    row = SimpleNamespace(
        carousel_shot_index=None,
        content_type="video/mp4",
        motion_video_prompt_auto=False,
        outfit_generation_id=None,
        video_backend="evolink",
    )
    job = _job(
        "motion_render_video",
        {"motion_control_wizard": "1", "seedance_variant": "standard"},
    )
    key, engine = resolve_generation_pipeline(row, job)
    assert key == "video_motion_control"
    assert engine == "Seedance 2.0 Sale"
