"""Тесты depth-map: URL модели и композиция сцены."""

from __future__ import annotations

import numpy as np

from app.services.motion_depth_map import (
    DEPTH_MAP_ALGO,
    MIDAS_URL,
    _compose_scene_depth_gray,
    motion_depth_video_path,
)


def test_midas_model_url_is_valid_release_asset():
    # Раньше midas_v21_small_256.onnx отдавал 404 → всегда срабатывал fallback.
    assert "model-small.onnx" in MIDAS_URL
    assert "v2_1" in MIDAS_URL


def test_depth_cache_filename_includes_algo_version():
    p = motion_depth_video_path(42, "abc123")
    assert p.name == f"abc123.depth.{DEPTH_MAP_ALGO}.mp4"


def test_compose_scene_keeps_environment_visible():
    depth = np.linspace(0, 10, 100, dtype=np.float32).reshape(10, 10)
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[2:8, 2:8] = 255
    gray = _compose_scene_depth_gray(depth, fg_mask=mask)
    # Угол кадра — окружение, не должен быть чёрным.
    assert gray[0, 0] > 0
    assert gray[5, 5] > gray[0, 0]


def test_compose_scene_person_brighter_than_background():
    depth = np.ones((20, 20), dtype=np.float32) * 3.0
    depth[8:12, 8:12] = 9.0
    depth[0:4, :] = 1.0
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[6:14, 6:14] = 255
    gray = _compose_scene_depth_gray(depth, fg_mask=mask)
    person = int(gray[10, 10])
    bg = int(gray[1, 1])
    assert person > bg


def test_compose_scene_clahe_boosts_internal_contrast():
    """CLAHE v4: ближняя «рука» внутри маски должна быть светлее дальнего «торса»."""
    depth = np.full((32, 32), 5.0, dtype=np.float32)
    depth[10:14, 22:28] = 9.0  # выступающая конечность справа
    depth[12:20, 10:18] = 4.0  # более дальний торс
    mask = np.zeros((32, 32), dtype=np.uint8)
    mask[8:24, 8:30] = 255
    gray = _compose_scene_depth_gray(depth, fg_mask=mask)
    limb = int(gray[12, 25])
    torso = int(gray[16, 14])
    assert limb > torso
