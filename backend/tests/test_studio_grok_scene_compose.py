"""Сборка сцен через Grok: выбор листов модели и разбор JSON."""

from __future__ import annotations

import json

from app.db.models import UserStudioModelImage
from app.services.studio_grok_scene_compose import (
    _parse_grok_compose_json,
    collect_model_images_for_grok_compose,
)
from app.services.studio_model_images import (
    select_grok_compose_wavespeed_identity_images,
    select_prompt_only_wavespeed_identity_images,
)


def _im(kind: str, id_: int = 1) -> UserStudioModelImage:
    return UserStudioModelImage(
        id=id_,
        studio_model_id=1,
        relative_path=f"uploads/studio/x/{kind}_{id_}.jpg",
        image_kind=kind,
    )


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


def test_prompt_only_identity_body_and_genitals_nsfw() -> None:
    imgs = [_im("turnaround", 1), _im("face", 2), _im("body", 3), _im("genitals", 4)]
    picked = select_prompt_only_wavespeed_identity_images(imgs, wave_profile="nsfw")
    kinds = [(im.image_kind or "") for im in picked]
    assert kinds == ["body", "genitals"]
    assert "turnaround" not in kinds
    assert "face" not in kinds


def test_prompt_only_identity_regular_body_only() -> None:
    imgs = [_im("turnaround", 1), _im("body", 2), _im("genitals", 3)]
    picked = select_prompt_only_wavespeed_identity_images(imgs, wave_profile="regular")
    assert len(picked) == 1
    assert picked[0].image_kind == "body"


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
