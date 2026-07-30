import pytest

from app.services.demo_watermark import apply_demo_watermark
from app.services.device_signal import build_device_signal, normalize_client_device_id


def test_normalize_client_device_id() -> None:
    assert normalize_client_device_id("abc12345") == "abc12345"
    assert normalize_client_device_id(" bad ") is None
    assert normalize_client_device_id("x" * 200) is None


def test_build_device_signal_stable_with_client_id() -> None:
    a = build_device_signal(client_ip="1.2.3.4", user_agent="Mozilla/5.0", device_id="client-abc12345")
    b = build_device_signal(client_ip="1.2.3.4", user_agent="Mozilla/5.0", device_id="client-abc12345")
    c = build_device_signal(client_ip="1.2.3.4", user_agent="Mozilla/5.0", device_id="other-abc12345")
    assert a.device_key == b.device_key
    assert a.device_key != c.device_key


def test_apply_demo_watermark_changes_png() -> None:
    pytest.importorskip("PIL")
    from io import BytesIO

    from PIL import Image

    img = Image.new("RGB", (320, 480), color=(120, 80, 160))
    buf = BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    out, ext, media = apply_demo_watermark(raw, ".png", "image/png")
    assert ext == ".png"
    assert media == "image/png"
    assert out != raw
    assert len(out) > 1000
