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


def test_selective_outline_cache_tag():
    from app.services.motion_selective_outline import selective_outline_cache_tag

    assert selective_outline_cache_tag() == "person-v1"


def test_canny_thresholds_from_edge_params():
    from app.services.motion_selective_outline import _canny_thresholds
    from app.services.motion_video_outline import EdgeOutlineParams

    params = EdgeOutlineParams(sigma=1.0, low=0.06, high=0.18, out_w=540, out_h=960)
    low, high = _canny_thresholds(params)
    assert 20 < low < high <= 220
