"""Tests for BoardStory reference layout."""

from app.services.studio_workflow_boardstory import (
    boardstory_slot_from_json,
    boardstory_slot_to_json,
    boardstory_tag_rules_text,
    classify_boardstory_ref_role,
    compute_boardstory_layout,
    BoardStoryImageSlot,
)


def test_classify_boardstory_ref_role():
    assert classify_boardstory_ref_role("clothes / outfit") == "clothing"
    assert classify_boardstory_ref_role("environment / room") == "environment"
    assert classify_boardstory_ref_role("pose donor") == "other"


def test_compute_boardstory_layout():
    layout = compute_boardstory_layout(2, has_clothing=True, has_environment=True, n_other=1)
    assert layout.identity_tag_expr == "@Image1–@Image2"
    assert layout.clothing_tag == "@Image3"
    assert layout.environment_tag == "@Image4"
    assert layout.other_image_indices == (5,)


def test_boardstory_tag_rules_fallback_to_video():
    layout = compute_boardstory_layout(1, has_clothing=False, has_environment=False)
    rules = boardstory_tag_rules_text(layout, has_motion=True)
    assert "@Video1" in rules
    assert "Wardrobe" in rules
    assert "Environment" in rules


def test_boardstory_slot_json_roundtrip():
    slot = BoardStoryImageSlot(kind="clothing", ref_id="abc123", role="outfit")
    data = boardstory_slot_to_json(slot)
    restored = boardstory_slot_from_json(data)
    assert restored is not None
    assert restored.ref_id == "abc123"
    assert restored.kind == "clothing"
