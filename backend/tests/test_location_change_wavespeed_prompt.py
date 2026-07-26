from app.services.studio_openai import finalize_wavespeed_studio_prompt
from app.services.studio_workflow_scenarios import (
    LOCATION_CHANGE_WAVESPEED_PREFIX,
    build_location_change_wavespeed_geometry_block,
)


def test_finalize_wavespeed_location_change_uses_correct_image_roles():
    out = finalize_wavespeed_studio_prompt(
        "Beach sunset behind the subject.",
        studio_mode="grok_compose",
        user_image_first=True,
        prompt_brief_mode="grok_main_prose",
        workflow_scenario_type="scenarioLocationChange",
        location_geometry_block="LOCKED FRAME GEOMETRY:\nPERSPECTIVE: low angle",
    )
    assert LOCATION_CHANGE_WAVESPEED_PREFIX.split("\n")[0] in out
    assert "Image 1 = photo-base EDIT CANVAS" in out
    assert "Image 2+ = location MATERIAL" in out
    assert "Re-project walls" in out
    assert "PERSPECTIVE: low angle" in out
    assert "Beach sunset" in out
    assert "LOCATION CHANGE ENFORCEMENT" in out
    assert "pose, crop, camera, background, light, wardrobe only" not in out
    assert "model identity" not in out.lower() or "model studio photos" not in out.lower()


def test_build_location_change_geometry_block_merges_refs():
    block = build_location_change_wavespeed_geometry_block(
        "FRAMING: selfie\nPERSPECTIVE: tilted",
        "LOCATION_MATERIALS:\nPLACE_TYPE: hotel lobby",
    )
    assert "LOCKED FRAME GEOMETRY" in block
    assert "FRAMING: selfie" in block
    assert "LOCATION_MATERIALS" in block
    assert "Rebuild background perspective" in block
