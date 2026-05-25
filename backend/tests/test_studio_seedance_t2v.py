from app.services.studio_seedance_t2v import assemble_seedance_t2v_prompt, truncate_seedance_t2v_prompt

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
