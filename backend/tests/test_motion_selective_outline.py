import numpy as np


def test_compose_person_outline_keeps_background():
    from app.services.motion_selective_outline import _compose_person_outline_frame

    frame = np.zeros((40, 60, 3), dtype=np.uint8)
    frame[:, :, 2] = 200  # синий фон
    person_mask = np.zeros((40, 60), dtype=np.uint8)
    person_mask[10:30, 20:45] = 255
    body_edges = np.zeros((40, 60), dtype=np.uint8)
    body_edges[15, 25] = 255

    out = _compose_person_outline_frame(
        frame,
        person_mask=person_mask,
        body_edges=body_edges,
        face_edges=None,
    )
    assert out[0, 0, 2] == 200
    assert tuple(out[15, 25]) == (0, 0, 0)
    assert tuple(out[12, 22]) == (255, 255, 255)


def test_compose_person_blur_keeps_background_and_blurs_person():
    from app.services.motion_selective_outline import _compose_person_blur_frame

    frame = np.zeros((40, 60, 3), dtype=np.uint8)
    frame[:, :, 2] = 200  # синий фон
    frame[10:30, 20:45] = (40, 120, 40)  # зелёный «человек»
    person_mask = np.zeros((40, 60), dtype=np.uint8)
    person_mask[10:30, 20:45] = 255

    out = _compose_person_blur_frame(
        frame,
        person_mask=person_mask,
        face_mask=None,
        sigma_body=6.0,
        sigma_face=3.0,
    )
    assert out[0, 0, 2] == 200
    assert tuple(out[15, 25]) != (40, 120, 40)
    assert out[15, 25, 1] > 40


def test_selective_outline_cache_tag_blur_default(monkeypatch):
    from app.config import settings
    from app.services.motion_selective_outline import selective_outline_cache_tag

    monkeypatch.setattr(settings, "motion_outline_person_style", "blur")
    assert selective_outline_cache_tag() == "person-blur-v1"


def test_selective_outline_cache_tag_outline(monkeypatch):
    from app.config import settings
    from app.services.motion_selective_outline import selective_outline_cache_tag

    monkeypatch.setattr(settings, "motion_outline_person_style", "outline")
    assert selective_outline_cache_tag() == "person-v1"


def test_motion_outline_prompt_uses_blur_by_default():
    from app.services.motion_video_outline import motion_outline_video_prompt_block

    text = motion_outline_video_prompt_block(appearance_refs="@Image1")
    assert "privacy-blurred" in text
    assert "white canvas" not in text


def test_motion_outline_prompt_outline_mode(monkeypatch):
    from app.config import settings
    from app.services.motion_video_outline import motion_outline_video_prompt_block

    monkeypatch.setattr(settings, "motion_outline_person_style", "outline")
    text = motion_outline_video_prompt_block(appearance_refs="@Image1")
    assert "white canvas" in text
    assert "privacy-blurred" not in text


def test_canny_thresholds_from_edge_params():
    from app.services.motion_selective_outline import _canny_thresholds
    from app.services.motion_video_outline import EdgeOutlineParams

    params = EdgeOutlineParams(sigma=1.0, low=0.06, high=0.18, out_w=540, out_h=960)
    low, high = _canny_thresholds(params)
    assert 20 < low < high <= 220
