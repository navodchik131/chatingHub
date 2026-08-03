"""Tests for character appearance profile v1 + visibility."""

import json

from app.services.studio_character_profile import (
    build_figure_anchor_from_profile,
    build_generation_packs,
    build_identity_line_from_profile,
    filter_model_profile_json_for_visibility,
    is_v1_character_profile,
)
from app.services.studio_reference_analysis import (
    ReferenceAnalysis,
    build_identity_visibility,
)


def _mask_character_v1() -> dict:
    return {
        "_meta": {"schema_name": "female_character_appearance", "schema_version": "1.0"},
        "identity": {
            "apparent_age": "25 (est)",
            "one_line_descriptor": "lean Nordic blonde, twin braids, tech respirator",
        },
        "skin": {"tone": "fair", "undertone": "neutral-warm"},
        "head_and_face": {
            "eyes": {
                "shape": "almond",
                "iris_color": "light blue with grey rim",
            },
            "nose": {"type": "undefined — hidden by mask"},
            "mouth": {"lip_type": "undefined — hidden by mask"},
        },
        "hair": {
            "color": "platinum blonde",
            "length": "waist-length",
            "default_style": "two braids in front of shoulders",
        },
        "body": {
            "height_cm": 172,
            "build": "lean athletic",
            "measurements_cm": {"waist": 60, "hips": 91},
            "anatomical_proportions": {
                "overall_proportion_notes": "narrow waist, fuller hips",
            },
        },
        "accessories": {
            "has_accessories": True,
            "items": [
                {
                    "name": "Techno half-face respirator",
                    "mandatory": True,
                    "always_worn": True,
                    "notes": "never removed; two filters and two antennas",
                }
            ],
        },
        "consistency": {
            "short_prompt_summary": (
                "Adult Nordic blonde 172cm, waist 60 hips 91, twin braids, "
                "always white-black respirator, light blue-grey eyes, no makeup."
            ),
            "negative_traits": ["no unmasked face", "no dark hair"],
        },
    }


def test_is_v1_character_profile():
    assert is_v1_character_profile(_mask_character_v1())
    assert not is_v1_character_profile({"model_profile": {"age": "25"}})


def test_build_generation_packs_from_v1():
    doc = _mask_character_v1()
    packs = build_generation_packs(doc)
    assert "waist 60 hips 91" in packs["figure_lock"]
    assert "platinum" in packs["hair_lock"].lower()
    assert "respirator" in packs["accessory_lock"].lower()
    assert packs["short_prompt_summary"]
    assert "no unmasked face" in packs["negative_lock"]


def test_generation_packs_replace_placeholder_locks():
    doc = _mask_character_v1()
    doc["generation_packs"] = {
        "figure_lock": "<FILL_OR_LEAVE_FOR_AUTO_DERIVE>",
        "face_lock": "<FILL_OR_LEAVE_FOR_AUTO_DERIVE>",
        "hair_lock": "<FILL_OR_LEAVE_FOR_AUTO_DERIVE>",
        "accessory_lock": "<FILL_OR_LEAVE_FOR_AUTO_DERIVE>",
        "short_prompt_summary": "<FILL_OR_LEAVE_FOR_AUTO_DERIVE>",
    }
    packs = build_generation_packs(doc)
    assert "FILL" not in json.dumps(packs)
    assert "waist 60 hips 91" in packs["figure_lock"]
    vis = build_identity_visibility(
        ReferenceAnalysis(face_in_frame=True, hair_in_frame=True, visible_regions=["FACE", "TORSO"])
    )
    line = build_identity_line_from_profile(json.dumps(doc), vis)
    assert "FILL" not in line
    assert "waist" in line.lower() or "build:" in line.lower()


def test_identity_line_face_visible_includes_mask():
    vis = build_identity_visibility(
        ReferenceAnalysis(face_in_frame=True, hair_in_frame=True, visible_regions=["FACE", "TORSO"])
    )
    line = build_identity_line_from_profile(json.dumps(_mask_character_v1()), vis)
    low = line.lower()
    assert "respirator" in low
    assert "build:" in low or "waist" in low
    assert "braid" in low or "platinum" in low
    assert len(line) <= 620


def test_identity_line_headless_omits_face_and_mask():
    vis = build_identity_visibility(
        ReferenceAnalysis(
            face_in_frame=False,
            hair_in_frame=False,
            visible_regions=["LEGS", "FEET"],
            framing_crop="legs only",
        )
    )
    line = build_identity_line_from_profile(json.dumps(_mask_character_v1()), vis)
    low = line.lower()
    assert "respirator" not in low
    assert "eyes" not in low
    assert "braid" not in low
    assert "visible regions" in low


def test_filter_v1_profile_headless_removes_head_sections():
    vis = build_identity_visibility(
        ReferenceAnalysis(face_in_frame=False, visible_regions=["LEGS"])
    )
    filtered = json.loads(
        filter_model_profile_json_for_visibility(json.dumps(_mask_character_v1()), vis) or "{}"
    )
    assert "head_and_face" not in filtered
    assert "accessories" not in filtered
    assert "body" not in filtered or vis.include_body_proportions


def test_legacy_profile_still_works():
    legacy = '{"model_profile":{"age":"26","ethnicity":"Slavic","body_type":"hourglass, narrow waist","hair":{"color":"brown","length":"long"}}}'
    vis = build_identity_visibility(
        ReferenceAnalysis(face_in_frame=True, hair_in_frame=True, visible_regions=["FACE", "TORSO"])
    )
    line = build_identity_line_from_profile(legacy, vis)
    assert "hourglass" in line.lower() or "build:" in line.lower()
    anchor = build_figure_anchor_from_profile(legacy, vis)
    assert anchor


def test_grok_figure_anchor_delegates_to_character_profile():
    from app.services.studio_prompt_bundle import grok_figure_anchor_from_profile

    legacy = '{"model_profile":{"body_type":"athletic build, long legs"}}'
    vis = build_identity_visibility(
        ReferenceAnalysis(face_in_frame=False, visible_regions=["LEGS", "FEET"])
    )
    a = grok_figure_anchor_from_profile(legacy, visibility=vis)
    assert "athletic" in a.lower() or "build:" in a.lower()
