from app.db.models import UserStudioModelImage
from app.services.studio_seedance_t2v import (
    append_seedance_identity_lock,
    assemble_seedance_t2v_prompt,
    assemble_seedance_video_edit_prompt,
    filter_model_images_for_seedance_video,
    prepare_motion_notes_for_seedance,
    seedance_model_identity_tag_expr,
    soften_seedance_provider_prompt,
    truncate_seedance_t2v_prompt,
)
from app.services.wavespeed_client import (
    wavespeed_is_sensitive_content_error,
    wavespeed_is_video_poll_timeout_error,
)


def test_truncate_prompt():
    long = "a" * 3500
    out = truncate_seedance_t2v_prompt(long, max_chars=3000)
    assert len(out) <= 3000
    assert out.endswith("…")


def test_assemble_with_start_frame():
    p = assemble_seedance_t2v_prompt(
        "She walks.",
        n_start_frame=1,
        n_model_images=1,
        n_motion_videos=1,
    )
    assert "@Image1" in p
    assert "@Image2" in p
    assert "opening still" in p.lower() or "t=0" in p.lower()
    assert "@Video1" in p
    assert "consistent character" in p.lower() or "same person" in p.lower()
    assert "facial identity" not in p.lower()
    assert "face/body" not in p.lower()


def test_assemble_wardrobe_from_start_frame_without_outfit_slot():
    p = assemble_seedance_t2v_prompt(
        "Dance.",
        n_start_frame=1,
        n_model_images=2,
        n_outfit_images=0,
    )
    assert "wardrobe at t=0" in p.lower()
    assert "match @image1" in p.lower()
    assert "ignore all clothing" not in p.lower()


def test_assemble_with_explicit_outfit_image():
    p = assemble_seedance_t2v_prompt(
        "Dance.",
        n_start_frame=1,
        n_model_images=2,
        n_outfit_images=1,
    )
    assert "wardrobe: match @image4" in p.lower()


def test_assemble_prompt_includes_image_tags():
    p = assemble_seedance_t2v_prompt(
        "She walks in the rain.",
        n_model_images=2,
        n_outfit_images=1,
        n_motion_videos=1,
    )
    assert "@Image1" in p
    assert "@Image2" in p
    assert "@Image3" in p
    assert "@Video1" in p
    assert "She walks in the rain." in p


def test_prepare_motion_notes_strips_biometric_lines():
    raw = (
        "[0.0s] blink\n"
        "skin tone warm olive\n"
        "camera push in\n"
        "facial identity: high cheekbones\n"
    )
    out = prepare_motion_notes_for_seedance(raw)
    assert out is not None
    assert "blink" in out
    assert "camera push" in out
    assert "skin tone" not in out.lower()
    assert "facial identity" not in out.lower()


def test_identity_tag_expr_with_start_frame():
    assert seedance_model_identity_tag_expr(1, 2) == "@Image2–@Image3"
    assert seedance_model_identity_tag_expr(0, 1) == "@Image1"


def test_append_identity_lock_uses_explicit_image_tags():
    out = append_seedance_identity_lock(
        "Cinematic scene.",
        n_start_frame=1,
        n_model_images=2,
        n_motion_videos=1,
    )
    assert "@Image2" in out
    assert "@Image3" in out
    assert out.count("Same character") >= 2
    assert "@Video1" in out
    assert "model references" not in out.lower()


def test_assemble_includes_identity_lock_with_video():
    p = assemble_seedance_t2v_prompt(
        "Dance.",
        n_start_frame=1,
        n_model_images=2,
        n_motion_videos=1,
    )
    assert "Same character" in p
    assert "@Image2" in p
    assert "@Video1" in p
    assert "appearance from" in p.lower() or "character look" in p.lower()


def test_video_edit_prompt_swap_identity():
    p = assemble_seedance_video_edit_prompt(
        "City promenade scene.",
        n_ref_images=3,
        motion_summary="[0.0s] fist raised",
    )
    assert "replace the performer" in p.lower()
    assert "reference images" in p.lower()
    assert "original video actor" in p.lower()
    assert "city promenade" in p.lower()


def test_filter_model_images_for_video_excludes_body():
    imgs = [
        UserStudioModelImage(id=1, image_kind="body"),
        UserStudioModelImage(id=2, image_kind="turnaround"),
        UserStudioModelImage(id=3, image_kind="face"),
        UserStudioModelImage(id=4, image_kind="genitals"),
    ]
    out = filter_model_images_for_seedance_video(imgs)
    kinds = [(im.image_kind or "") for im in out]
    assert kinds == ["turnaround", "face"]
    assert filter_model_images_for_seedance_video(imgs, minimal=True)[0].image_kind == "turnaround"
    with_body = filter_model_images_for_seedance_video(imgs, include_body=True)
    assert len(with_body) == 3
    assert [im.image_kind for im in with_body] == ["turnaround", "face", "body"]


def test_wavespeed_poll_timeout_detector():
    assert wavespeed_is_video_poll_timeout_error("WaveSpeed: timeout waiting for video")
    assert not wavespeed_is_video_poll_timeout_error("WaveSpeed task failed")


def test_wavespeed_sensitive_detector():
    assert wavespeed_is_sensitive_content_error(
        "Content flagged as potentially sensitive. Please try different prompts or images."
    )
    assert not wavespeed_is_sensitive_content_error("Insufficient credits")


def test_append_identity_lock_zh():
    out = append_seedance_identity_lock(
        "电影感场景。",
        n_start_frame=1,
        n_model_images=2,
        n_motion_videos=1,
        language="zh",
    )
    assert "@Image2" in out
    assert "整段视频" in out
    assert out.count("整段视频") >= 2


def test_soften_provider_prompt():
    raw = (
        "Same person — identity via @Image2 (face/body/hair). "
        "Never adopt the reference video actor's face or identity. "
        "IGNORE all clothing on @Image2."
    )
    out = soften_seedance_provider_prompt(raw)
    assert "face/body" not in out.lower()
    assert "never adopt" not in out.lower()
    assert "ignore all clothing" not in out.lower()
    assert "character via" in out.lower()
