import pytest
from fastapi import HTTPException

from app.services.safe_url import assert_safe_https_url


def test_assert_safe_https_url_rejects_http() -> None:
    with pytest.raises(HTTPException, match="https"):
        assert_safe_https_url("http://example.com/x")


def test_assert_safe_https_url_rejects_localhost() -> None:
    with pytest.raises(HTTPException):
        assert_safe_https_url("https://localhost/secret")


def test_assert_safe_https_url_rejects_private_ip() -> None:
    with pytest.raises(HTTPException):
        assert_safe_https_url("https://127.0.0.1/")

    with pytest.raises(HTTPException):
        assert_safe_https_url("https://10.0.0.1/")


def test_assert_safe_https_url_allows_public_host(monkeypatch: pytest.MonkeyPatch) -> None:
    import ipaddress

    def _fake_resolve(host: str):
        _ = host
        return [ipaddress.ip_address("93.184.216.34")]

    monkeypatch.setattr("app.services.safe_url._resolve_host_ips", _fake_resolve)
    assert assert_safe_https_url("https://cdn.example.com/image.jpg").startswith("https://")
