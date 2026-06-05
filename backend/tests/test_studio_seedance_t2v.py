from app.services.studio_seedance_t2v import (
    assemble_seedance_t2v_prompt,
    prepare_motion_notes_for_seedance,
    soften_seedance_provider_prompt,
    truncate_seedance_t2v_prompt,
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
    assert "same character" in p.lower()
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
