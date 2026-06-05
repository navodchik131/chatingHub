from io import BytesIO

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app.services.studio_ai_metadata_strip import strip_ai_metadata_from_image_bytes


def _png_with_sd_parameters() -> bytes:
    img = Image.new("RGB", (16, 16), color=(40, 80, 120))
    pnginfo = PngInfo()
    pnginfo.add_text("parameters", "Steps: 20, Sampler: Euler a, CFG scale: 7")
    buf = BytesIO()
    img.save(buf, format="PNG", pnginfo=pnginfo)
    return buf.getvalue()


pytest.importorskip("remove_ai_watermarks")


def test_strip_removes_sd_parameters_chunk() -> None:
    raw = _png_with_sd_parameters()
    cleaned, stripped = strip_ai_metadata_from_image_bytes(raw, ext=".png")
    assert stripped is True
    assert cleaned != raw
    with Image.open(BytesIO(cleaned)) as img:
        assert "parameters" not in img.info


def test_strip_skips_clean_png() -> None:
    buf = BytesIO()
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(buf, format="PNG")
    raw = buf.getvalue()
    cleaned, stripped = strip_ai_metadata_from_image_bytes(raw, ext=".png")
    assert stripped is False
    assert cleaned == raw
