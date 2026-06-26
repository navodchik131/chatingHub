"""Tests for BoardStory reference layout."""

from app.services.studio_workflow_boardstory import (
    BoardStoryImageSlot,
    append_boardstory_prompt_enforcement,
    boardstory_clothing_env_swap_mode,
    boardstory_model_swap_lock_text,
    boardstory_slot_from_json,
    boardstory_slot_to_json,
    boardstory_tag_rules_text,
    boardstory_video_only_swap_mode,
    build_boardstory_clothing_env_swap_prompt,
    build_boardstory_video_only_swap_prompt,
    classify_boardstory_ref_role,
    compute_boardstory_layout,
    filter_boardstory_identity_image,
    filter_boardstory_turnaround_image,
    filter_model_images_for_boardstory,
)


def test_classify_boardstory_ref_role():
    assert classify_boardstory_ref_role("clothes / outfit") == "clothing"
    assert classify_boardstory_ref_role("environment / room") == "environment"
    assert classify_boardstory_ref_role("pose donor") == "other"


def test_compute_boardstory_layout_full():
    layout = compute_boardstory_layout(
        has_identity=True,
        has_turnaround=True,
        has_clothing=True,
        has_environment=True,
        n_other=1,
    )
    assert layout.identity_tag == "@Image1"
    assert layout.turnaround_tag == "@Image2"
    assert layout.clothing_tag == "@Image3"
    assert layout.environment_tag == "@Image4"
    assert layout.other_image_indices == (5,)


def test_boardstory_tag_rules_fallback_to_video():
    layout = compute_boardstory_layout(
        has_identity=True,
        has_turnaround=True,
        has_clothing=False,
        has_environment=False,
    )
    rules = boardstory_tag_rules_text(
        layout,
        has_motion=True,
        clothing_from_video=True,
        environment_from_video=True,
    )
    assert "@Video1" in rules
    assert "@Image1" in rules
    assert "@Image2" in rules
    assert "body proportions" in rules.lower()


def test_boardstory_tag_rules_model_replacement():
    layout = compute_boardstory_layout(
        has_identity=True,
        has_turnaround=True,
        has_clothing=True,
        has_environment=True,
    )
    rules = boardstory_tag_rules_text(
        layout, has_motion=True, send_video_reference=True
    )
    assert "MODEL REPLACEMENT" in rules
    assert "@Image3" in rules
    assert "@Image4" in rules


def test_boardstory_tag_rules_no_video_ref_mode():
    layout = compute_boardstory_layout(
        has_identity=True,
        has_turnaround=True,
        has_clothing=True,
        has_environment=True,
    )
    rules = boardstory_tag_rules_text(
        layout, has_motion=False, send_video_reference=False
    )
    assert "@Video1" not in rules
    assert "NO @Video tags" in rules
    assert "@Image2" in rules


def test_boardstory_model_swap_lock():
    layout = compute_boardstory_layout(
        has_identity=True,
        has_turnaround=True,
        has_clothing=True,
        has_environment=True,
    )
    lock = boardstory_model_swap_lock_text(layout)
    assert "MODEL SWAP" in lock
    assert "@Image2" in lock
    assert "@Image3" in lock


def test_append_boardstory_prompt_enforcement_no_video():
    layout = compute_boardstory_layout(
        has_identity=True,
        has_turnaround=True,
        has_clothing=True,
        has_environment=True,
    )
    out = append_boardstory_prompt_enforcement(
        "She reads a book calmly. Wardrobe from @Video1.",
        layout=layout,
        clothing_from_video=False,
        environment_from_video=False,
        send_video_reference=False,
    )
    assert "@Video1" not in out
    assert "Wardrobe from @Image3" in out


def test_append_boardstory_prompt_enforcement_adds_replace():
    layout = compute_boardstory_layout(
        has_identity=True,
        has_turnaround=True,
        has_clothing=True,
        has_environment=True,
    )
    out = append_boardstory_prompt_enforcement(
        "She reads a book calmly.",
        layout=layout,
        clothing_from_video=False,
        environment_from_video=False,
        send_video_reference=True,
    )
    assert "Replace" in out or "Wardrobe" in out


def test_boardstory_video_only_swap_mode():
    assert boardstory_video_only_swap_mode(
        clothing_ref=None,
        environment_ref=None,
        generate_clothing_from_video=False,
        generate_environment_from_video=False,
        send_video_reference=True,
    )
    assert not boardstory_video_only_swap_mode(
        clothing_ref=BoardStoryImageSlot(kind="clothing", ref_id="x"),
        environment_ref=None,
        generate_clothing_from_video=False,
        generate_environment_from_video=False,
        send_video_reference=True,
    )


def test_build_boardstory_video_only_swap_prompt():
    out = build_boardstory_video_only_swap_prompt(user_notes="Calm mood.")
    assert "Use @Video1 exclusively" in out
    assert "Use @Image1 exclusively" in out
    assert "Use @Image2 exclusively" in out
    assert "body proportions" in out.lower()
    assert "MOTION CHOREOGRAPHY AND TIMING" not in out


def test_build_boardstory_clothing_env_swap_prompt():
    out = build_boardstory_clothing_env_swap_prompt(user_notes="Soft light.")
    assert "Use @Image2 exclusively as the body proportions" in out
    assert "Use @Image3 exclusively as the clothing" in out
    assert "Use @Image4 for the environment" in out


def test_filter_boardstory_identity_image_prefers_body():
    from app.db.models import UserStudioModelImage

    imgs = [
        UserStudioModelImage(id=1, image_kind="turnaround"),
        UserStudioModelImage(id=2, image_kind="body"),
        UserStudioModelImage(id=3, image_kind="face"),
    ]
    out = filter_boardstory_identity_image(imgs)
    assert len(out) == 1
    assert out[0].image_kind == "body"
    assert filter_model_images_for_boardstory(imgs) == out


def test_filter_boardstory_turnaround_image():
    from app.db.models import UserStudioModelImage

    imgs = [
        UserStudioModelImage(id=1, image_kind="turnaround"),
        UserStudioModelImage(id=2, image_kind="body"),
    ]
    out = filter_boardstory_turnaround_image(imgs)
    assert len(out) == 1
    assert out[0].image_kind == "turnaround"


def test_filter_boardstory_identity_empty_without_body():
    from app.db.models import UserStudioModelImage

    imgs = [
        UserStudioModelImage(id=1, image_kind="turnaround"),
        UserStudioModelImage(id=2, image_kind="face"),
    ]
    assert filter_boardstory_identity_image(imgs) == []


def test_boardstory_slot_json_roundtrip():
    slot = BoardStoryImageSlot(kind="clothing", ref_id="abc123", role="outfit")
    data = boardstory_slot_to_json(slot)
    restored = boardstory_slot_from_json(data)
    assert restored is not None
    assert restored.ref_id == "abc123"
    assert restored.kind == "clothing"
