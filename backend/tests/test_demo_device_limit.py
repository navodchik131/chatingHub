from app.services.demo_device_limit import demo_device_limit
from app.services.device_signal import build_device_signal


def test_demo_device_limit_default() -> None:
    assert demo_device_limit() >= 0


def test_device_key_differs_without_client_id() -> None:
    a = build_device_signal(client_ip="1.1.1.1", user_agent="UA-A", device_id="device-aaaa1111")
    b = build_device_signal(client_ip="1.1.1.1", user_agent="UA-B", device_id="device-bbbb2222")
    assert a.device_key != b.device_key
