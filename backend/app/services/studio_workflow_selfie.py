"""Workflow-нода «Селфи»: жёсткие указания для Grok и JSON photography."""

from __future__ import annotations

from typing import Any

SELFIE_GROK_NOTES_BLOCK = """
=== WORKFLOW: ARM-LENGTH FRONT-CAMERA SELFIE (AUTHORITATIVE) ===
This workflow node OVERRIDES any conflicting camera wording in USER_NOTES or scene references.
- Capture type: arm-length smartphone selfie from the subject's extended arm / front-facing camera.
- POV: camera held in the subject's near hand at ~0.35–0.65 m; subject looks into the front lens.
- Framing: typical selfie crop (face/upper body or arm-reach full body); slight wide-angle phone stretch at arm length is OK.
- NOT allowed: friend-held rear camera, third-party photographer, shot from across the room at 1–2 m without arm reach.
- Phone visible at frame edge or in the near hand is expected when holding the phone for a selfie.
- Ignore or rewrite lines like "rear camera", "friend took the photo", "someone else photographed her" — they contradict this node.
=== END WORKFLOW SELFIE ===
""".strip()


def append_selfie_capture_grok_notes(description: str) -> str:
    base = (description or "").strip()
    if SELFIE_GROK_NOTES_BLOCK in base:
        return base
    if base:
        return f"{base}\n\n{SELFIE_GROK_NOTES_BLOCK}"
    return SELFIE_GROK_NOTES_BLOCK


def selfie_negative_extras() -> str:
    return (
        "friend photographing subject, third-person rear camera snapshot, "
        "shot by another person at distance, DSLR portrait photographer, "
        "candid photo taken by someone else"
    )


def photography_json_for_selfie(aspect: str, *, with_pose_reference: bool) -> dict[str, Any]:
    photography: dict[str, Any] = {
        "aspect_ratio": aspect,
        "capture_type": "arm-length front-camera selfie from extended arm",
        "camera_style": "smartphone front-facing selfie POV — subject holds phone",
        "device": "front camera (selfie lens)",
        "camera_distance": "~0.35–0.65 m arm reach",
        "framing": "typical phone selfie crop; face prominent, arm-length perspective",
        "lighting": "ambient incidental light on face — no ring-light glamour",
        "snapshot_authenticity": "casual handheld front-camera selfie, slight wide-angle stretch OK",
    }
    if with_pose_reference:
        photography["pose_from_image_1"] = (
            "body pose and limb angles only from reference — "
            "camera MUST stay front selfie POV at arm length, not reference camera"
        )
    return photography


def must_keep_for_selfie(*, with_pose_reference: bool) -> list[str]:
    if with_pose_reference:
        return [
            "Identity from model reference images on visible skin",
            "Arm-length front-camera selfie POV — overrides reference camera if different",
            "Pose limb angles from reference image 1 where compatible with arm-reach selfie",
        ]
    return [
        "One real person; identity from model reference images on visible skin",
        "Arm-length front-camera selfie POV from extended arm — NOT friend/rear-camera shot",
        "Phone selfie realism per realism_engine — natural grain, no plastic skin",
    ]
