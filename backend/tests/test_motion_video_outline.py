from app.services.motion_video_outline import (
    choose_edge_params,
    motion_outline_video_prompt_block,
    output_size_for_source,
)


def test_output_size_portrait_landscape_square():
    assert output_size_for_source(1080, 1920) == (540, 960)
    assert output_size_for_source(1920, 1080) == (960, 540)
    assert output_size_for_source(720, 720) == (720, 720)


def test_choose_edge_params_by_contrast():
    assert choose_edge_params(30) == (1.6, 0.04, 0.12)
    assert choose_edge_params(80) == (0.8, 0.10, 0.30)
    assert choose_edge_params(50) == (1.0, 0.06, 0.18)


def test_motion_outline_prompt_block():
    text = motion_outline_video_prompt_block(appearance_refs="@Image1, @Image2 and @Image3")
    assert "@Video1" in text
    assert "edge-outline" in text
    assert "@Image1" in text
