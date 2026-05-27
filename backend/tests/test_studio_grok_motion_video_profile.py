import json

from app.services.studio_grok_motion import _compact_model_profile_for_video_grok


def test_compact_profile_strips_face_catalog() -> None:
    raw = {
        "subject": {
            "identity": {
                "age": "25",
                "ethnicity": "East Asian",
                "face_features": "almond eyes, full lips, high cheekbones",
                "body_type": "slim athletic",
                "skin": {"tone": "warm beige", "imperfections": "light freckles"},
                "hair": {"length": "long", "style_default": "straight"},
                "distinctive_marks": "small mole left cheek",
            },
            "expression": {"eyes": "wide", "mouth": "smile"},
        }
    }
    out = _compact_model_profile_for_video_grok(json.dumps(raw))
    parsed = json.loads(out.split("\n", 1)[0])
    ident = parsed["subject"]["identity"]
    assert "face_features" not in ident
    assert "ethnicity" not in ident
    assert "distinctive_marks" not in ident
    assert "skin" not in ident
    assert ident["body_type"] == "slim athletic"
    assert ident["hair"]["length"] == "long"
    assert "expression" not in parsed["subject"]
    assert "VIDEO:" in out


def test_compact_profile_passthrough_non_json() -> None:
    prose = "Long hair model, casual style."
    assert _compact_model_profile_for_video_grok(prose) == prose
