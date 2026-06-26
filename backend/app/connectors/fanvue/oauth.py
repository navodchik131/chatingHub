"""Fanvue OAuth 2.0 + PKCE: authorize URL, token exchange, refresh, /users/me."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class FanvueOAuthError(Exception):
    def __init__(self, message: str, *, status: int = 0, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def fanvue_oauth_configured() -> bool:
    return bool(
        (settings.fanvue_client_id or "").strip()
        and (settings.fanvue_client_secret or "").strip()
    )


def fanvue_oauth_redirect_uri() -> str:
    base = (settings.public_app_url or "").strip().rstrip("/")
    if not base:
        raise FanvueOAuthError("PUBLIC_APP_URL is not configured")
    return f"{base}/api/integrations/fanvue/oauth/callback"


def fanvue_oauth_scopes() -> str:
    raw = (settings.fanvue_oauth_scopes or "").strip()
    if raw:
        return raw
    return "openid offline_access offline read:self read:chat write:chat"


def generate_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def build_fanvue_authorize_url(*, state: str, code_challenge: str) -> str:
    if not fanvue_oauth_configured():
        raise FanvueOAuthError("Fanvue OAuth is not configured on the server")
    params = {
        "client_id": settings.fanvue_client_id.strip(),
        "redirect_uri": fanvue_oauth_redirect_uri(),
        "response_type": "code",
        "scope": fanvue_oauth_scopes(),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_base = (settings.fanvue_oauth_authorize_url or "https://auth.fanvue.com/oauth2/auth").strip()
    return f"{auth_base}?{urlencode(params)}"


async def _post_token_form(data: dict[str, str]) -> dict[str, Any]:
    token_url = (settings.fanvue_oauth_token_url or "https://auth.fanvue.com/oauth2/token").strip()
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if r.status_code >= 400:
        log.warning("fanvue oauth token failed: %s %s", r.status_code, r.text[:800])
        raise FanvueOAuthError(
            "Fanvue token request failed",
            status=r.status_code,
            body=r.text[:2000],
        )
    try:
        payload = r.json()
    except Exception as e:
        raise FanvueOAuthError("Fanvue token response is not JSON") from e
    if not isinstance(payload, dict):
        raise FanvueOAuthError("Fanvue token response must be a JSON object")
    return payload


async def exchange_fanvue_authorization_code(
    *,
    code: str,
    code_verifier: str,
) -> dict[str, Any]:
    if not fanvue_oauth_configured():
        raise FanvueOAuthError("Fanvue OAuth is not configured on the server")
    return await _post_token_form(
        {
            "grant_type": "authorization_code",
            "client_id": settings.fanvue_client_id.strip(),
            "client_secret": settings.fanvue_client_secret.strip(),
            "code": code.strip(),
            "redirect_uri": fanvue_oauth_redirect_uri(),
            "code_verifier": code_verifier.strip(),
        }
    )


async def refresh_fanvue_access_token(*, refresh_token: str) -> dict[str, Any]:
    if not fanvue_oauth_configured():
        raise FanvueOAuthError("Fanvue OAuth is not configured on the server")
    return await _post_token_form(
        {
            "grant_type": "refresh_token",
            "client_id": settings.fanvue_client_id.strip(),
            "client_secret": settings.fanvue_client_secret.strip(),
            "refresh_token": refresh_token.strip(),
        }
    )


async def fetch_fanvue_current_user(access_token: str) -> dict[str, Any]:
    token = (access_token or "").strip()
    if not token:
        raise FanvueOAuthError("empty access token")
    base = (settings.fanvue_api_base or "https://api.fanvue.com").rstrip("/")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Fanvue-API-Version": settings.fanvue_api_version,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"{base}/users/me", headers=headers)
    if r.status_code >= 400:
        log.warning("fanvue users/me failed: %s %s", r.status_code, r.text[:800])
        raise FanvueOAuthError(
            "Fanvue /users/me failed",
            status=r.status_code,
            body=r.text[:2000],
        )
    try:
        payload = r.json()
    except Exception as e:
        raise FanvueOAuthError("Fanvue /users/me response is not JSON") from e
    if not isinstance(payload, dict):
        raise FanvueOAuthError("Fanvue /users/me must be a JSON object")
    return payload
