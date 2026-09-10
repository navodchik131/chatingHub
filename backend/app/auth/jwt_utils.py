from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings


def create_access_token(user_id: int, *, token_version: int = 0) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(int(user_id)),
        "tv": int(token_version),
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token_claims(token: str) -> tuple[int, int]:
    try:
        data = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        sub = data.get("sub")
        if sub is None:
            raise ValueError("no sub")
        user_id = int(sub)
        token_version = int(data.get("tv") or 0)
        return user_id, token_version
    except (JWTError, ValueError, TypeError) as e:
        raise ValueError("invalid token") from e


def decode_token(token: str) -> str:
    """Legacy: только user id (без проверки tv — предпочитайте user_from_access_token)."""
    user_id, _tv = decode_token_claims(token)
    return str(user_id)
