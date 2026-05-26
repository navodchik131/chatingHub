import json

from app.services.studio_prompt_bundle import prepare_positive_prompt_json


def test_compact_strips_scene_keeps_body():
    sample = {
        "subject": {
            "description": (
                "A 22-year-old attractive Caucasian woman with vibrant purple wavy hair, "
                "standing on an outdoor villa balcony with her back facing the camera"
            ),
            "body": {
                "frame": "curvy athletic hourglass figure",
                "chest": "full, round natural C/D-cup bust",
                "legs": "long toned legs",
            },
            "hair": {"color": "vibrant purple", "style": "wavy"},
            "pose": {"position": "standing on balcony"},
            "clothing": {"top": {"type": "beige halter"}},
        },
        "photography": {"aspect_ratio": "3:4"},
        "background": {"setting": "villa balcony"},
        "constraints": {
            "must_keep": ["back view", "glass railing"],
            "avoid": ["selfie", "bedroom", "deformed hands"],
        },
        "negative_prompt": "selfie, bedroom, deformed hands",
    }
    pos, neg = prepare_positive_prompt_json(
        json.dumps(sample),
        brief_mode="compact_pose_image",
        model_profile_text=None,
    )
    data = json.loads(pos)
    assert "identity_reference" in data
    assert data["scene_from_reference_image"]["pose_and_composition"] == (
        "from_pose_reference_input_image_only"
    )
    assert "C/D-cup" in data["identity_reference"]["body_proportions"]
    assert "balcony" not in pos.lower()
    assert "bedroom" not in neg.lower()
    assert "deformed" in neg.lower()


def test_compact_includes_scene_notes_when_reference_provided():
    ref = (
        "POSE: low-angle selfie, arm extended toward lens\n"
        "FRAMING: face and shoulders, kitchen background\n"
        "CLOTHING: grey crop top"
    )
    pos, _ = prepare_positive_prompt_json(
        '{"identity_reference":{"subject":"test"}}',
        brief_mode="compact_pose_image",
        model_profile_text=None,
        reference_scene_description=ref,
    )
    data = json.loads(pos)
    notes = data["scene_from_reference_image"].get("pose_reference_notes", "")
    assert "low-angle" in notes.lower()
    assert "kitchen" in notes.lower()


def test_compact_nude_reference_wardrobe_and_negative():
    ref = (
        "POSE: standing three-quarter\n"
        "CLOTHING: no clothing visible; subject nude\n"
        "FRAMING: full body"
    )
    pos, neg = prepare_positive_prompt_json(
        "{}",
        brief_mode="compact_pose_image",
        model_profile_text=None,
        reference_scene_description=ref,
    )
    data = json.loads(pos)
    assert data.get("pose_reference_is_nude_or_minimal") is True
    assert "nude" in data.get("wardrobe_coverage", "").lower()
    assert "sportswear" in neg.lower() or "character sheet" in neg.lower()
