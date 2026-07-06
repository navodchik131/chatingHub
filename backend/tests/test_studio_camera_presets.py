"""Загрузка пресетов камер — bundled JSON при перекрытом томе data/."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.studio_camera_presets import _preset_paths, list_camera_presets


def test_list_iphone_presets_from_json_at_least_23():
    iphones = list_camera_presets(iphone_only=True)
    assert len(iphones) >= 23
    ids = {p["id"] for p in iphones}
    assert "iphone_11" in ids
    assert "iphone_16_pro_max" in ids


def test_bundled_presets_used_when_data_path_missing(tmp_path: Path):
    bundled = tmp_path / "bundled.json"
    bundled.write_text(
        (Path(__file__).resolve().parents[1] / "data" / "studio_camera_presets.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    missing = tmp_path / "missing" / "studio_camera_presets.json"

    with patch(
        "app.services.studio_camera_presets._preset_paths",
        return_value=[missing, bundled],
    ):
        iphones = list_camera_presets(iphone_only=True)

    assert len(iphones) >= 23
