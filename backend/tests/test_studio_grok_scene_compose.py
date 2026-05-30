"""Сборка сцен через Grok: выбор листов модели и разбор JSON."""

from __future__ import annotations

import json

from app.db.models import UserStudioModelImage
from app.config import BACKEND_DIR
from app.services.studio_grok_scene_compose import (
    _grok_prompt_file_candidates,
    _parse_grok_compose_json,
    collect_model_images_for_grok_compose,
    load_grok_scene_compose_text_system,
)
from app.services.studio_model_images import (
    select_grok_compose_wavespeed_identity_images,
    select_prompt_only_wavespeed_identity_images,
)
from app.services.studio_prompt_bundle import (
    append_negative_to_wavespeed_prompt,
    build_grok_scene_positive_json,
    build_grok_text_scene_positive_json,
)


def _im(kind: str, id_: int = 1) -> UserStudioModelImage:
    return UserStudioModelImage(
        id=id_,
        studio_model_id=1,
        relative_path=f"uploads/studio/x/{kind}_{id_}.jpg",
        image_kind=kind,
    )


def test_grok_text_system_loads_from_bundled_prompts() -> None:
    bundled = (
        BACKEND_DIR / "_bundled_prompts" / "grok_scene_compose_text_system.txt"
    ).resolve()
    assert bundled.is_file(), "bundled text prompt must ship in repo / Docker image"
    text = load_grok_scene_compose_text_system()
    assert "TEXT_SCENE_ONLY" in text or "text-only" in text.lower()


def test_grok_prompt_candidates_include_bundled_fallback() -> None:
    paths = _grok_prompt_file_candidates(
        "data/prompts/grok_scene_compose_text_system.txt",
        "grok_scene_compose_text_system.txt",
    )
    assert any("_bundled_prompts" in str(p) for p in paths)
    assert len(paths) >= 2


def test_collect_nsfw_includes_genitals() -> None:
    imgs = [
        _im("turnaround", 1),
        _im("genitals", 2),
        _im("face", 3),
    ]
    labeled = collect_model_images_for_grok_compose(imgs, wave_profile="nsfw")
    labels = [lb for lb, _ in labeled]
    assert labels[0] == "CHARACTER_SHEET_CLOTHED"
    assert "ANATOMY_REFERENCE_NUDE" in labels
    assert "FACE_IDENTITY" in labels


def test_collect_regular_skips_genitals() -> None:
    imgs = [_im("turnaround", 1), _im("genitals", 2), _im("face", 3)]
    labeled = collect_model_images_for_grok_compose(imgs, wave_profile="regular")
    labels = [lb for lb, _ in labeled]
    assert "ANATOMY_REFERENCE_NUDE" not in labels
    assert "CHARACTER_SHEET_CLOTHED" in labels


def test_wavespeed_identity_prefers_body_and_face() -> None:
    imgs = [_im("turnaround", 1), _im("face", 2), _im("body", 3)]
    picked = select_grok_compose_wavespeed_identity_images(imgs)
    kinds = [(im.image_kind or "") for im in picked]
    assert "body" in kinds
    assert "face" in kinds
    assert kinds.index("body") < kinds.index("face")


def test_wavespeed_identity_body_without_face() -> None:
    imgs = [_im("turnaround", 1), _im("body", 2)]
    picked = select_grok_compose_wavespeed_identity_images(imgs)
    assert len(picked) >= 1
    assert picked[0].image_kind == "body"


def test_wavespeed_identity_nude_includes_genitals() -> None:
    imgs = [_im("body", 1), _im("genitals", 2), _im("face", 3)]
    picked = select_grok_compose_wavespeed_identity_images(imgs, pose_reference_nude=True)
    kinds = [(im.image_kind or "") for im in picked]
    assert "body" in kinds
    assert "genitals" in kinds
    assert "face" in kinds


def test_prompt_only_identity_body_face_genitals_nsfw() -> None:
    imgs = [_im("turnaround", 1), _im("face", 2), _im("body", 3), _im("genitals", 4)]
    picked = select_prompt_only_wavespeed_identity_images(imgs, wave_profile="nsfw")
    kinds = [(im.image_kind or "") for im in picked]
    assert kinds == ["body", "face", "genitals"]
    assert "turnaround" not in kinds


def test_prompt_only_identity_regular_body_and_face() -> None:
    imgs = [_im("turnaround", 1), _im("body", 2), _im("genitals", 3), _im("face", 4)]
    picked = select_prompt_only_wavespeed_identity_images(imgs, wave_profile="regular")
    kinds = [(im.image_kind or "") for im in picked]
    assert kinds == ["body", "face"]


def test_grok_compose_pose_ref_json_has_realism_engine_and_no_suffix_negative() -> None:
    positive, neg = build_grok_scene_positive_json(
        "Mirror selfie, nude on bed edge, same pose as reference.",
        model_profile_text='{"model_profile":{"identity_lock_keywords":"test"}}',
        extra_negative="reference sitter body, wrong bust size",
        reference_scene_description="seated nude, mirror selfie, window side light",
        with_pose_reference=True,
    )
    data = json.loads(positive)
    assert data.get("reference_scene_lock", "").startswith("seated")
    assert data.get("realism_engine") is not None
    assert data["photography"].get("pose_lock")
    ws = append_negative_to_wavespeed_prompt(positive, neg, brief_mode="grok_composed")
    assert "[NEGATIVE_PROMPT]" not in ws
    assert "realism_engine" in ws
    assert "reference sitter body" in data["negative_prompt"]


def test_grok_text_scene_json_has_realism_engine_and_no_suffix_negative() -> None:
    positive, neg = build_grok_text_scene_positive_json(
        "A woman in a sunlit kitchen, casual phone snapshot.",
        model_profile_text='{"model_profile":{"identity_lock_keywords":"test"}}',
        extra_negative="wrong person, heavy fake bokeh",
    )
    data = json.loads(positive)
    assert "scene_brief" in data
    assert data.get("realism_engine") is not None
    assert "photo_realism" in json.dumps(data["realism_engine"])
    assert data.get("negative_prompt")
    assert "heavy fake bokeh" in data["negative_prompt"] or "bokeh" in data["negative_prompt"]
    ws = append_negative_to_wavespeed_prompt(positive, neg, brief_mode="grok_composed_text")
    assert "[NEGATIVE_PROMPT]" not in ws
    assert "realism_engine" in ws


def test_parse_grok_compose_json() -> None:
    raw = json.dumps(
        {
            "wavespeed_scene_prompt": "A woman in soft window light, seated pose.",
            "reference_scene_lock": "seated, three-quarter, warm side light",
            "negative_prompt": "wrong person, blur",
        }
    )
    out = _parse_grok_compose_json(raw)
    assert "seated" in out.wavespeed_scene_prompt
    assert out.reference_scene_lock.startswith("seated")
    assert "blur" in out.negative_prompt
