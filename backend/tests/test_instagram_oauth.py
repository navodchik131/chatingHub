"""Tests for Instagram OAuth helpers."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.connectors.instagram.oauth import (
    exchange_instagram_long_lived_token,
    resolve_instagram_profile_ids,
)


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


def test_exchange_instagram_long_lived_token_uses_post():
    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.json.return_value = {
        "access_token": "long-token",
        "token_type": "bearer",
        "expires_in": 5184000,
    }

    client = AsyncMock()
    client.post = AsyncMock(return_value=ok_response)
    client.get = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    async def _run():
        with patch("app.connectors.instagram.oauth.settings") as mock_settings:
            mock_settings.instagram_app_secret = "secret"
            mock_settings.instagram_graph_api_version = "v21.0"
            with patch("app.connectors.instagram.oauth.httpx.AsyncClient", return_value=client):
                return await exchange_instagram_long_lived_token("short-token")

    payload = asyncio.run(_run())

    assert payload["access_token"] == "long-token"
    client.post.assert_awaited()
    assert client.post.await_args.args[0] == "https://graph.instagram.com/access_token"
    assert client.post.await_args.kwargs["data"]["grant_type"] == "ig_exchange_token"
