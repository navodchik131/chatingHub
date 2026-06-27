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
    rules = boardstory_tag_rules_text(
        layout,
        has_motion=True,
        clothing_from_video=True,
        environment_from_video=True,
    )
    assert "@Video1" in rules
    assert "Wardrobe" in rules
    assert "Room" in rules
    assert "@Image1" in rules
    assert "@Image2" not in rules


def test_boardstory_tag_rules_model_replacement():
    layout = compute_boardstory_layout(1, has_clothing=True, has_environment=True)
    rules = boardstory_tag_rules_text(
        layout, has_motion=True, send_video_reference=True
    )
    assert "MODEL REPLACEMENT" in rules
    assert "@Video1" in rules
    assert "@Image2" in rules


def test_boardstory_tag_rules_no_video_ref_mode():
    layout = compute_boardstory_layout(1, has_clothing=True, has_environment=True)
    rules = boardstory_tag_rules_text(
        layout, has_motion=False, send_video_reference=False
    )
    assert "@Video1" not in rules
    assert "NO @Video tags" in rules
    assert "@Image2" in rules


def test_boardstory_model_swap_lock():
    layout = compute_boardstory_layout(1, has_clothing=True, has_environment=True)
    lock = boardstory_model_swap_lock_text(layout)
    assert "MODEL REPLACEMENT" in lock
    assert "@Video1" in lock


def test_append_boardstory_prompt_enforcement_no_video():
    layout = compute_boardstory_layout(1, has_clothing=True, has_environment=True)
    out = append_boardstory_prompt_enforcement(
        "She reads a book calmly. Wardrobe from @Video1.",
        layout=layout,
        clothing_from_video=False,
        environment_from_video=False,
        send_video_reference=False,
    )
    assert "@Video1" not in out
    assert "Wardrobe from @Image2" in out


def test_append_boardstory_prompt_enforcement_adds_replace():
    layout = compute_boardstory_layout(1, has_clothing=True, has_environment=True)
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
    assert not boardstory_video_only_swap_mode(
        clothing_ref=None,
        environment_ref=None,
        generate_clothing_from_video=True,
        generate_environment_from_video=False,
        send_video_reference=True,
    )


def test_build_boardstory_video_only_swap_prompt():
    out = build_boardstory_video_only_swap_prompt(
        user_notes="Calm mood.",
    )
    assert "MODEL REPLACEMENT" in out
    assert "MOTION ONLY (@Video1)" in out
    assert "IDENTITY (@Image1)" in out
    assert "USER_DIRECTION" in out
    assert "@Video1" in out
    assert "Do not copy the @Video1 performer identity" in out
    assert "Use @Video1 exclusively" not in out


def test_build_boardstory_video_only_swap_prompt_ignores_timeline_in_notes_only():
    out = build_boardstory_video_only_swap_prompt(user_notes="")
    assert "[0 s]" not in out


def test_boardstory_clothing_env_swap_mode():
    clothing = BoardStoryImageSlot(kind="clothing", ref_id="c1")
    environment = BoardStoryImageSlot(kind="environment", ref_id="e1")
    assert boardstory_clothing_env_swap_mode(
        clothing_ref=clothing,
        environment_ref=environment,
        send_video_reference=True,
    )
    assert not boardstory_clothing_env_swap_mode(
        clothing_ref=clothing,
        environment_ref=None,
        send_video_reference=True,
    )


def test_build_boardstory_clothing_env_swap_prompt():
    out = build_boardstory_clothing_env_swap_prompt(
        user_notes="Soft light.",
    )
    assert "MODEL REPLACEMENT" in out
    assert "CLOTHING (@Image2)" in out
    assert "MOTION ONLY (@Video1)" in out
    assert "Do not copy the @Video1 performer identity" in out
    assert "[1 s]" not in out


def test_filter_model_images_for_boardstory_identity_refs():
    from app.db.models import UserStudioModelImage
    from app.services.studio_workflow_boardstory import filter_model_images_for_boardstory

    imgs = [
        UserStudioModelImage(id=1, image_kind="turnaround"),
        UserStudioModelImage(id=2, image_kind="body"),
        UserStudioModelImage(id=3, image_kind="face"),
    ]
    out = filter_model_images_for_boardstory(imgs)
    assert len(out) == 3
    kinds = [im.image_kind for im in out]
    assert kinds == ["turnaround", "face", "body"]


def test_filter_model_images_for_boardstory_fallback_without_body():
    from app.db.models import UserStudioModelImage
    from app.services.studio_workflow_boardstory import filter_model_images_for_boardstory

    imgs = [
        UserStudioModelImage(id=1, image_kind="turnaround"),
        UserStudioModelImage(id=2, image_kind="face"),
    ]
    out = filter_model_images_for_boardstory(imgs)
    assert len(out) == 2
    assert {im.image_kind for im in out} == {"turnaround", "face"}


def test_boardstory_slot_json_roundtrip():
    slot = BoardStoryImageSlot(kind="clothing", ref_id="abc123", role="outfit")
    data = boardstory_slot_to_json(slot)
    restored = boardstory_slot_from_json(data)
    assert restored is not None
    assert restored.ref_id == "abc123"
    assert restored.kind == "clothing"
