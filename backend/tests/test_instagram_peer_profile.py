"""Tests for Instagram peer display helpers."""

from app.services.instagram_peer_profile import (
    format_instagram_peer_display,
    instagram_peer_display_is_placeholder,
)


def test_format_instagram_peer_display_prefers_username():
    assert format_instagram_peer_display({"username": "anna_k", "name": "Anna"}, "123") == "@anna_k"


def test_format_instagram_peer_display_falls_back_to_name():
    assert format_instagram_peer_display({"name": "Anna Klein"}, "123") == "Anna Klein"


def test_format_instagram_peer_display_falls_back_to_short_id():
    out = format_instagram_peer_display(None, "1008227122345")
    assert out == "Instagram · 100822712234"


def test_instagram_peer_display_is_placeholder_detects_legacy():
    assert instagram_peer_display_is_placeholder("Instagram 1008227122", "1008227122345")
    assert instagram_peer_display_is_placeholder("1008227122345", "1008227122345")
    assert instagram_peer_display_is_placeholder("Instagram · 100822712234", "1008227122345")


def test_instagram_peer_display_is_placeholder_rejects_real_username():
    assert not instagram_peer_display_is_placeholder("@anna_k", "1008227122345")
    assert not instagram_peer_display_is_placeholder("Anna Klein", "1008227122345")
