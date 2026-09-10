"""HttpOnly cookie для JWT-сессии (дополнение к Bearer для API-клиентов)."""

from __future__ import annotations

from fastapi import Request, Response

from app.config import settings

TOKEN_COOKIE_NAME = "chating_token"
TOKEN_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # совпадает с jwt_expire_minutes по умолчанию


def _cookie_secure() -> bool:
    return (settings.public_app_url or "").strip().lower().startswith("https://")


def read_auth_cookie(request: Request) -> str | None:
    token = (request.cookies.get(TOKEN_COOKIE_NAME) or "").strip()
    return token or None


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=token,
        max_age=TOKEN_COOKIE_MAX_AGE,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
    )
