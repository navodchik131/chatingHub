"""Instagram Business Login OAuth."""

from __future__ import annotations

import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class InstagramOAuthError(Exception):
    def __init__(self, message: str, *, status: int = 0, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def instagram_oauth_configured() -> bool:
    return bool(
        (settings.instagram_app_id or "").strip()
        and (settings.instagram_app_secret or "").strip()
    )


def instagram_oauth_redirect_uri() -> str:
    base = (settings.public_app_url or "").strip().rstrip("/")
    if not base:
        raise InstagramOAuthError("PUBLIC_APP_URL is not configured")
    return f"{base}/api/integrations/instagram/oauth/callback"


def instagram_oauth_scopes() -> str:
    raw = (settings.instagram_oauth_scopes or "").strip()
    return raw or "instagram_business_basic,instagram_business_manage_messages"


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def build_instagram_authorize_url(*, state: str) -> str:
    if not instagram_oauth_configured():
        raise InstagramOAuthError("Instagram OAuth is not configured on the server")
    params = {
        "client_id": settings.instagram_app_id.strip(),
        "redirect_uri": instagram_oauth_redirect_uri(),
        "response_type": "code",
        "scope": instagram_oauth_scopes(),
        "state": state,
    }
    return f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"


def _graph_version() -> str:
    return (settings.instagram_graph_api_version or "v21.0").strip().lstrip("v")


def _normalize_token_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return payload


async def exchange_instagram_authorization_code(*, code: str) -> dict[str, Any]:
    if not instagram_oauth_configured():
        raise InstagramOAuthError("Instagram OAuth is not configured on the server")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.instagram.com/oauth/access_token",
            data={
                "client_id": settings.instagram_app_id.strip(),
                "client_secret": settings.instagram_app_secret.strip(),
                "grant_type": "authorization_code",
                "redirect_uri": instagram_oauth_redirect_uri(),
                "code": code.strip(),
            },
        )
    if r.status_code >= 400:
        log.warning("instagram oauth token failed: %s %s", r.status_code, r.text[:800])
        raise InstagramOAuthError(
            "Instagram token request failed",
            status=r.status_code,
            body=r.text[:2000],
        )
    try:
        payload = r.json()
    except Exception as e:
        raise InstagramOAuthError("Instagram token response is not JSON") from e
    if not isinstance(payload, dict):
        raise InstagramOAuthError("Instagram token response must be a JSON object")
    short = _normalize_token_payload(payload)
    access = str(short.get("access_token") or "").strip()
    if not access:
        raise InstagramOAuthError("Instagram token response missing access_token")
    long_payload = await exchange_instagram_long_lived_token(access)
    user_id = short.get("user_id")
    if user_id is not None:
        long_payload["user_id"] = user_id
    return long_payload


async def exchange_instagram_long_lived_token(short_lived_token: str) -> dict[str, Any]:
    token = (short_lived_token or "").strip()
    if not token:
        raise InstagramOAuthError("empty short-lived token")
    ver = _graph_version()
    params = {
        "grant_type": "ig_exchange_token",
        "client_secret": settings.instagram_app_secret.strip(),
        "access_token": token,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"https://graph.instagram.com/v{ver}/access_token", params=params)
    if r.status_code >= 400:
        log.warning("instagram long-lived token failed: %s %s", r.status_code, r.text[:800])
        raise InstagramOAuthError(
            "Instagram long-lived token exchange failed",
            status=r.status_code,
            body=r.text[:2000],
        )
    try:
        payload = r.json()
    except Exception as e:
        raise InstagramOAuthError("Instagram long-lived response is not JSON") from e
    if not isinstance(payload, dict):
        raise InstagramOAuthError("Instagram long-lived response must be a JSON object")
    access = str(payload.get("access_token") or "").strip()
    if not access:
        raise InstagramOAuthError("Instagram long-lived response missing access_token")
    return payload


async def refresh_instagram_access_token(access_token: str) -> dict[str, Any]:
    token = (access_token or "").strip()
    if not token:
        raise InstagramOAuthError("empty access token")
    ver = _graph_version()
    params = {
        "grant_type": "ig_refresh_token",
        "access_token": token,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"https://graph.instagram.com/v{ver}/refresh_access_token", params=params)
    if r.status_code >= 400:
        log.warning("instagram token refresh failed: %s %s", r.status_code, r.text[:800])
        raise InstagramOAuthError(
            "Instagram token refresh failed",
            status=r.status_code,
            body=r.text[:2000],
        )
    try:
        payload = r.json()
    except Exception as e:
        raise InstagramOAuthError("Instagram refresh response is not JSON") from e
    if not isinstance(payload, dict):
        raise InstagramOAuthError("Instagram refresh response must be a JSON object")
    access = str(payload.get("access_token") or "").strip()
    if not access:
        raise InstagramOAuthError("Instagram refresh response missing access_token")
    return payload


def resolve_instagram_profile_ids(
    profile: dict[str, Any],
    token_payload: dict[str, Any] | None = None,
) -> tuple[str, str | None]:
    """Return primary Graph API id and optional alternate id from /me.

    Meta returns two identifiers (`id` and `user_id`); webhooks may use either.
    """
    payload = token_payload or {}
    candidates: list[str] = []
    for raw in (profile.get("id"), profile.get("user_id"), payload.get("user_id")):
        value = str(raw or "").strip()
        if value and value != "0" and value not in candidates:
            candidates.append(value)
    if not candidates:
        return "", None
    primary = candidates[0]
    alt = candidates[1] if len(candidates) > 1 else None
    return primary, alt


def resolve_instagram_account_id(
    profile: dict[str, Any],
    token_payload: dict[str, Any] | None = None,
) -> str:
    primary, _alt = resolve_instagram_profile_ids(profile, token_payload)
    return primary


async def subscribe_instagram_webhooks(
    access_token: str,
    *,
    fields: str = "messages",
) -> dict[str, Any]:
    """Enable per-account webhook delivery after Instagram Login OAuth."""
    token = (access_token or "").strip()
    if not token:
        raise InstagramOAuthError("empty access token")
    ver = _graph_version()
    params = {
        "subscribed_fields": fields,
        "access_token": token,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"https://graph.instagram.com/v{ver}/me/subscribed_apps",
            params=params,
        )
    if r.status_code >= 400:
        log.warning(
            "instagram subscribed_apps failed: %s %s",
            r.status_code,
            r.text[:800],
        )
        raise InstagramOAuthError(
            "Instagram webhook subscription failed",
            status=r.status_code,
            body=r.text[:2000],
        )
    try:
        payload = r.json()
    except Exception as e:
        raise InstagramOAuthError("Instagram subscribed_apps response is not JSON") from e
    if not isinstance(payload, dict):
        raise InstagramOAuthError("Instagram subscribed_apps response must be a JSON object")
    log.info("instagram subscribed_apps ok fields=%s success=%s", fields, payload.get("success"))
    return payload


async def fetch_instagram_profile(access_token: str) -> dict[str, Any]:
    token = (access_token or "").strip()
    if not token:
        raise InstagramOAuthError("empty access token")
    ver = _graph_version()
    params = {
        "fields": "id,username,user_id",
        "access_token": token,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"https://graph.instagram.com/v{ver}/me", params=params)
    if r.status_code >= 400:
        log.warning("instagram /me failed: %s %s", r.status_code, r.text[:800])
        raise InstagramOAuthError(
            "Instagram /me failed",
            status=r.status_code,
            body=r.text[:2000],
        )
    try:
        payload = r.json()
    except Exception as e:
        raise InstagramOAuthError("Instagram /me response is not JSON") from e
    if not isinstance(payload, dict):
        raise InstagramOAuthError("Instagram /me must be a JSON object")
    return payload
