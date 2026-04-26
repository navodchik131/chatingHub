from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings


def create_model_image_access_token(*, user_id: int, image_id: int, minutes: int = 20) -> str:
    """Краткоживущий JWT, чтобы WaveSpeed мог скачать референс по публичному URL."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "typ": "studio_model_img",
        "uid": user_id,
        "iid": image_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_model_image_access_token(token: str) -> tuple[int, int]:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError("invalid token") from e
    if data.get("typ") != "studio_model_img":
        raise ValueError("wrong token type")
    uid = data.get("uid")
    iid = data.get("iid")
    if uid is None or iid is None:
        raise ValueError("missing claims")
    return int(uid), int(iid)
