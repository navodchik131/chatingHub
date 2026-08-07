from __future__ import annotations

from types import SimpleNamespace

from app.services.partner import (
    partner_login_redirect_url,
    partner_public_redirect_url,
    partner_redirect_url,
)


def _partner(slug: str = "stat") -> SimpleNamespace:
    return SimpleNamespace(partner_slug=slug)


def test_partner_public_redirect_home() -> None:
    url = partner_public_redirect_url(_partner(), source_tag="shedevils", dest="home")
    assert url.endswith("/?pref=stat&src=shedevils") or url.endswith("/?pref=stat&src=shedevils")


def test_partner_public_redirect_pricing() -> None:
    url = partner_public_redirect_url(_partner(), source_tag="ig", dest="pricing")
    assert "/pricing?pref=stat&src=ig" in url


def test_partner_redirect_home_is_public() -> None:
    url = partner_redirect_url(_partner(), source_tag="shedevils", dest="home")
    assert "/login" not in url
    assert "pref=stat" in url
    assert "src=shedevils" in url


def test_partner_redirect_pricing_is_public() -> None:
    url = partner_redirect_url(_partner(), source_tag="x", dest="pricing")
    assert "/pricing?" in url
    assert "/login" not in url


def test_partner_redirect_studio_goes_to_login() -> None:
    url = partner_redirect_url(_partner(), source_tag="tg", dest="studio")
    assert "/login?" in url
    assert "pref=stat" in url
    assert "src=tg" in url
    assert "next=/workspace/images" in url


def test_partner_redirect_chats_goes_to_login() -> None:
    url = partner_redirect_url(_partner(), source_tag="yt", dest="chats")
    assert "/login?" in url
    assert "next=/workspace/dialogs" in url


def test_partner_login_redirect_url_unchanged_for_workspace() -> None:
    url = partner_login_redirect_url(_partner(), source_tag="a", dest="studio")
    assert url.endswith("/login?pref=stat&src=a&to=studio&next=/workspace/images")
