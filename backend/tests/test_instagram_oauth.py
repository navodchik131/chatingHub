"""Tests for Instagram OAuth helpers."""

from app.connectors.instagram.oauth import resolve_instagram_profile_ids


def test_resolve_instagram_profile_ids_prefers_user_id():
    profile = {
        "id": "2787389990220688",
        "user_id": "17841449063344747",
        "username": "mantik.alice",
    }
    primary, alt = resolve_instagram_profile_ids(profile)
    assert primary == "17841449063344747"
    assert alt == "2787389990220688"


def test_resolve_instagram_profile_ids_only_app_scoped_id():
    profile = {"id": "2787389990220688", "username": "mantik.alice"}
    primary, alt = resolve_instagram_profile_ids(profile)
    assert primary == "2787389990220688"
    assert alt is None


def test_resolve_instagram_profile_ids_token_payload_fallback():
    profile = {"id": "2787389990220688", "username": "mantik.alice"}
    token_payload = {"user_id": "17841449063344747"}
    primary, alt = resolve_instagram_profile_ids(profile, token_payload)
    assert primary == "17841449063344747"
    assert alt == "2787389990220688"
