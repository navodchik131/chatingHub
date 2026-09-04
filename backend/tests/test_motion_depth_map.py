"""Тесты depth-map: URL модели и нормализация."""

from __future__ import annotations

import numpy as np

from app.services.motion_depth_map import (
    DEPTH_MAP_ALGO,
    MIDAS_URL,
    _normalize_depth_to_gray,
    motion_depth_video_path,
)


def test_midas_model_url_is_valid_release_asset():
    # Раньше midas_v21_small_256.onnx отдавал 404 → всегда срабатывал fallback.
    assert "model-small.onnx" in MIDAS_URL
    assert "v2_1" in MIDAS_URL


def test_depth_cache_filename_includes_algo_version():
    p = motion_depth_video_path(42, "abc123")
    assert p.name == f"abc123.depth.{DEPTH_MAP_ALGO}.mp4"


def test_normalize_depth_masks_background_to_black():
    depth = np.linspace(0, 10, 100, dtype=np.float32).reshape(10, 10)
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[2:8, 2:8] = 255
    gray = _normalize_depth_to_gray(depth, fg_mask=mask)
    assert gray[0, 0] == 0
    assert gray[5, 5] > 0
    assert gray[5, 5] <= 255


def test_normalize_depth_foreground_has_contrast():
    depth = np.ones((20, 20), dtype=np.float32) * 5.0
    depth[8:12, 8:12] = 20.0
    mask = np.full((20, 20), 255, dtype=np.uint8)
    gray = _normalize_depth_to_gray(depth, fg_mask=mask)
    center = int(gray[10, 10])
    edge = int(gray[0, 0])
    assert center > edge
