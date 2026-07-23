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
    select_model_scene_wavespeed_identity_images,
    select_prompt_only_wavespeed_identity_images,
)
from app.services.studio_prompt_bundle import (
    PRIORITY_IDENTITY_OVER_POSE,
    append_negative_to_wavespeed_prompt,
    build_grok_scene_positive_json,
    build_grok_text_scene_positive_json,
    grok_figure_anchor_from_profile,
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


def test_wavespeed_identity_clothed_pose_body_and_face_no_turnaround() -> None:
    imgs = [_im("turnaround", 1), _im("face", 2), _im("body", 3)]
    picked = select_grok_compose_wavespeed_identity_images(imgs, pose_reference_nude=False)
    kinds = [(im.image_kind or "") for im in picked]
    assert kinds == ["body", "face"]
    assert "turnaround" not in kinds


def test_wavespeed_identity_body_without_face() -> None:
    imgs = [_im("turnaround", 1), _im("body", 2)]
    picked = select_grok_compose_wavespeed_identity_images(imgs)
    assert len(picked) >= 1
    assert picked[0].image_kind == "body"


def test_strip_donor_identity_from_scene_prose() -> None:
    from app.services.studio_prompt_bundle import strip_donor_identity_from_scene_prose

    raw = (
        "A 23-year-old Eurasian woman with long golden blonde wavy hair, warm golden tan skin, "
        "large natural C-cup breasts, very toned flat abs and narrow waist takes a mirror selfie "
        "in a luxury high-rise hotel room at night. She stands in front of a large mirror wearing "
        "only a tight white mini skirt and black sheer thigh-high stockings."
    )
    out = strip_donor_identity_from_scene_prose(raw)
    low = out.lower()
    assert "blonde" not in low
    assert "c-cup" not in low
    assert "eurasian" not in low
    assert "golden tan skin" not in low
    assert "mirror selfie" in low
    assert "white mini skirt" in low


def test_grok_main_prose_prepare_strips_donor_identity() -> None:
    from app.services.studio_prompt_bundle import prepare_positive_prompt_json

    donor = (
        "A 23-year-old Eurasian woman with long golden blonde hair takes a mirror selfie at night."
    )
    positive, _ = prepare_positive_prompt_json(
        donor,
        brief_mode="grok_main_prose",
        model_profile_text='{"model_profile":{"body_type":"hourglass"}}',
    )
    assert "blonde" not in positive.lower()
    assert "Model identity" in positive
    assert PRIORITY_IDENTITY_OVER_POSE in positive
    assert "mirror selfie" in positive.lower()


def test_wan_identity_nude_pose_includes_body_face_genitals() -> None:
    from app.services.studio_model_images import select_wan_identity_images_with_pose_ref

    imgs = [_im("body", 1), _im("genitals", 2), _im("face", 3), _im("turnaround", 4)]
    picked = select_wan_identity_images_with_pose_ref(imgs, pose_reference_nude=True)
    kinds = [(im.image_kind or "") for im in picked]
    assert kinds == ["body", "face", "genitals"]


def test_wavespeed_identity_nude_pose_includes_body_face_genitals() -> None:
    imgs = [_im("body", 1), _im("genitals", 2), _im("face", 3), _im("turnaround", 4)]
    picked = select_grok_compose_wavespeed_identity_images(imgs, pose_reference_nude=True)
    kinds = [(im.image_kind or "") for im in picked]
    assert kinds == ["body", "face", "genitals"]
    assert "turnaround" not in kinds


def test_prompt_only_identity_body_face_genitals_nsfw() -> None:
    imgs = [_im("turnaround", 1), _im("face", 2), _im("body", 3), _im("genitals", 4)]
    picked = select_prompt_only_wavespeed_identity_images(imgs, wave_profile="nsfw")
    kinds = [(im.image_kind or "") for im in picked]
    assert kinds == ["body", "face", "genitals"]
    assert "turnaround" not in kinds


def test_model_scene_identity_includes_turnaround() -> None:
    imgs = [
        _im("turnaround", 1),
        _im("body", 2),
        _im("face", 3),
        _im("genitals", 4),
    ]
    picked = select_model_scene_wavespeed_identity_images(imgs, wave_profile="nsfw")
    kinds = [(im.image_kind or "").lower() for im in picked]
    assert "turnaround" in kinds
    assert "body" in kinds


def test_prompt_only_identity_regular_body_and_face() -> None:
    imgs = [_im("turnaround", 1), _im("body", 2), _im("genitals", 3), _im("face", 4)]
    picked = select_prompt_only_wavespeed_identity_images(imgs, wave_profile="regular")
    kinds = [(im.image_kind or "") for im in picked]
    assert kinds == ["body", "face"]


def test_grok_figure_anchor_from_profile() -> None:
    anchor = grok_figure_anchor_from_profile(
        '{"model_profile":{"body_type":"curvy hourglass, full bust, narrow waist"}}'
    )
    assert "FIGURE_LOCK" not in anchor or "Model body" in anchor
    assert "hourglass" in anchor.lower() or "curvy" in anchor.lower()


def test_model_scene_wan_prefix_uses_main_prose() -> None:
    from app.services.studio_openai import finalize_wavespeed_studio_prompt

    main = finalize_wavespeed_studio_prompt(
        "A woman in warm window light, seated on the bed edge, three-quarter view.",
        studio_mode="model_scene",
        user_image_first=False,
        prompt_brief_mode="grok_main_prose",
    )
    assert "One model from attached reference photos" in main
    assert "JSON" not in main
    assert "face-swap" not in main.lower()


def test_parse_grok_main_prose_output() -> None:
    from app.services.studio_grok_scene_compose import _parse_grok_main_prose_output

    raw = (
        "---PROMPT---\n"
        "Warm side light on a mirror selfie, model in beige ribbed crop top, "
        "standing with weight on left leg, phone at chest height.\n"
        "---NEGATIVE---\n"
        "wrong person, blur, watermark\n"
        "---VISIBLE---\n"
        "full body, face visible"
    )
    out = _parse_grok_main_prose_output(raw)
    assert "mirror selfie" in out.wavespeed_scene_prompt
    assert "blur" in out.negative_prompt
    assert "face visible" in out.reference_scene_lock


def test_grok_main_system_prefers_photo_brief_not_catalog() -> None:
    from app.services.studio_grok_scene_compose import load_grok_scene_compose_main_system

    text = load_grok_scene_compose_main_system()
    low = text.lower()
    assert "photo brief" in low or "not an image-analysis report" in low
    assert "PROMPT_REGION_POLICY" in text
    assert "End the prose with one short sentence naming" not in text
    from app.services.studio_prompt_bundle import (
        append_negative_to_wavespeed_prompt,
        prepare_positive_prompt_json,
    )

    positive, neg = prepare_positive_prompt_json(
        "Seated on sofa, soft window light, casual phone snapshot.",
        brief_mode="grok_main_prose",
        model_profile_text='{"model_profile":{"body_type":"athletic"}}',
        extra_negative="wrong person",
        wavespeed_identity_legend="Image 2: character sheet; Image 3: body",
    )
    assert not positive.strip().startswith("{")
    assert "Image 2: character sheet" in positive
    assert "Model identity" in positive
    assert PRIORITY_IDENTITY_OVER_POSE in positive
    assert "Seated on sofa" in positive
    assert "Photoreal phone look" in positive or "Capture realism:" in positive
    assert "pores" in positive.lower() or "vellus" in positive.lower() or "grain" in positive.lower()
    assert "on-camera phone flash" not in positive.lower()
    ws = append_negative_to_wavespeed_prompt(positive, neg, brief_mode="grok_main_prose")
    assert "[NEGATIVE_PROMPT]" not in ws
    assert '"realism_engine"' not in ws


def test_phone_candid_flash_triggers_only_for_indoor_night() -> None:
    from app.services.studio_openai import (
        format_realism_engine_for_prose_prompt,
        phone_candid_scene_triggers,
    )

    assert phone_candid_scene_triggers("sunny window light, outdoor terrace") == ""
    assert "flash" in phone_candid_scene_triggers("bedroom at night, dim lamp").lower()
    day = format_realism_engine_for_prose_prompt("sunny balcony daylight")
    night = format_realism_engine_for_prose_prompt("bedroom at night")
    assert "on-camera phone flash" not in day.lower()
    assert "on-camera phone flash" in night.lower()


def test_model_scene_wan_prefix_differs_from_grok_compose() -> None:
    from app.services.studio_openai import finalize_wavespeed_studio_prompt

    grok = finalize_wavespeed_studio_prompt(
        "FIGURE_LOCK: curvy hourglass. Mirror selfie on bed.",
        studio_mode="grok_compose",
        user_image_first=True,
        prompt_brief_mode="grok_composed",
    )
    main = finalize_wavespeed_studio_prompt(
        "FIGURE_LOCK: curvy hourglass. Mirror selfie on bed.",
        studio_mode="model_scene",
        user_image_first=False,
        prompt_brief_mode="grok_main_prose",
    )
    assert "Image 1:" in grok
    assert "One model from attached reference photos" in main
    assert grok != main


def test_grok_main_prose_with_pose_uses_model_scene_prefix_not_reference_order() -> None:
    from app.services.studio_openai import finalize_wavespeed_studio_prompt

    out = finalize_wavespeed_studio_prompt(
        "Attached model reference photos — Image 2: face likeness\n\nMirror selfie at night.",
        studio_mode="model_scene",
        user_image_first=True,
        prompt_brief_mode="grok_main_prose",
    )
    assert "Image 1:" in out
    assert "model identity wins" in out.lower()
    assert "REFERENCE_IMAGE_ORDER" not in out


def test_wavespeed_identity_legend_offsets_pose_image() -> None:
    from types import SimpleNamespace

    from app.services.studio_model_images import wavespeed_identity_image_legend

    imgs = [
        SimpleNamespace(image_kind="face"),
        SimpleNamespace(image_kind="turnaround"),
    ]
    assert wavespeed_identity_image_legend(imgs) == (
        "Image 1: face likeness and skin tone; Image 2: character sheet — face, hair, clothed silhouette"
    )
    assert wavespeed_identity_image_legend(imgs, image_index_offset=1) == (
        "Image 2: face likeness and skin tone; Image 3: character sheet — face, hair, clothed silhouette"
    )


def test_grok_compose_pose_ref_json_has_realism_engine_and_no_suffix_negative() -> None:
    positive, neg = build_grok_scene_positive_json(
        "Mirror selfie, nude on bed edge, same pose as reference.",
        model_profile_text='{"model_profile":{"identity_lock_keywords":"test"}}',
        extra_negative="reference sitter body, wrong bust size, deformed hands",
        reference_scene_description="seated nude, mirror selfie, window side light",
        with_pose_reference=True,
    )
    data = json.loads(positive)
    assert "reference_scene_lock" not in data
    assert data.get("realism_engine") is not None
    assert data["photography"].get("pose_from_image_1")
    assert PRIORITY_IDENTITY_OVER_POSE.lower() in data["scene_brief"].lower()
    ws = append_negative_to_wavespeed_prompt(positive, neg, brief_mode="grok_composed")
    assert "[NEGATIVE_PROMPT]" not in ws
    assert "realism_engine" in ws
    assert "negative_prompt" not in data
    assert "deformed" in neg.lower()
    assert "reference sitter body" not in neg.lower()
    assert "wrong bust" not in neg.lower()


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
    assert "negative_prompt" not in data
    assert "bokeh" in neg.lower() or "wrong person" in neg.lower()
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


def test_nano_face_swap_grok_main_prose_uses_identity_first_prefix() -> None:
    from app.services.studio_openai import finalize_nano_banana_studio_prompt

    prose = (
        "Attached model reference photos — Image 1: face likeness and skin tone\n\n"
        "Close-up selfie outdoors at night under stadium lights."
    )
    out = finalize_nano_banana_studio_prompt(
        prose,
        studio_mode="face_swap",
        user_photo_edit_first=False,
        user_pose_reference_is_last=True,
        prompt_brief_mode="grok_main_prose",
    )
    assert "intentional FACE SWAP" in out
    assert "LAST" in out
    assert "LAST_INPUT_IMAGE" in out
    assert "Attached images = one saved model" not in out


def test_wan_face_swap_grok_main_prose_keeps_scene_as_image_1() -> None:
    """NSFW / WAN / Seedream(nsfw): scene stays first; face_swap prefix wins over grok_main_prose."""
    from app.services.studio_openai import finalize_wavespeed_studio_prompt

    prose = (
        "Attached model reference photos — Image 2: face likeness and skin tone\n\n"
        "Close-up selfie outdoors at night under stadium lights."
    )
    out = finalize_wavespeed_studio_prompt(
        prose,
        studio_mode="face_swap",
        user_image_first=True,
        prompt_brief_mode="grok_main_prose",
    )
    assert "[FACE_SWAP — WAN]" in out
    assert "Image 1" in out
    assert "SOURCE snapshot" in out
    assert "model identity wins" not in out.lower() or "FACE_SWAP" in out
    # Must not fall through to generic model-scene / generate-scene prose prefix alone.
    assert out.startswith("[FACE_SWAP — WAN]")
