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


def create_generation_image_access_token(
    *, user_id: int, generation_id: int, days: int = 30
) -> str:
    """JWT для <img src> и публичной выдачи архивной картинки (без Bearer)."""
    expire = datetime.now(timezone.utc) + timedelta(days=days)
    payload = {
        "typ": "studio_gen_img",
        "uid": user_id,
        "gid": generation_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_generation_image_access_token(token: str) -> tuple[int, int]:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError("invalid token") from e
    if data.get("typ") != "studio_gen_img":
        raise ValueError("wrong token type")
    uid = data.get("uid")
    gid = data.get("gid")
    if uid is None or gid is None:
        raise ValueError("missing claims")
    return int(uid), int(gid)


def create_pose_reference_access_token(
    *, user_id: int, file_id: str, minutes: int = 45
) -> str:
    """JWT для разового референса позы (multipart), чтобы WaveSpeed скачал по HTTPS."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "typ": "studio_pose_ref",
        "uid": user_id,
        "fid": str(file_id)[:80],
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_pose_reference_access_token(token: str) -> tuple[int, str]:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError("invalid token") from e
    if data.get("typ") != "studio_pose_ref":
        raise ValueError("wrong token type")
    uid = data.get("uid")
    fid = data.get("fid")
    if uid is None or fid is None:
        raise ValueError("missing claims")
    return int(uid), str(fid)


def create_motion_video_access_token(
    *, user_id: int, file_id: str, minutes: int = 90
) -> str:
    """JWT для driving video: WaveSpeed качает по публичному HTTPS."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "typ": "studio_motion_vid",
        "uid": user_id,
        "fid": str(file_id)[:80],
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_motion_video_access_token(token: str) -> tuple[int, str]:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError("invalid token") from e
    if data.get("typ") != "studio_motion_vid":
        raise ValueError("wrong token type")
    uid = data.get("uid")
    fid = data.get("fid")
    if uid is None or fid is None:
        raise ValueError("missing claims")
    return int(uid), str(fid)


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


def create_workflow_ref_access_token(
    *, user_id: int, ref_id: str, minutes: int = 90
) -> str:
    """JWT для workflow reference image — WaveSpeed скачивает по HTTPS."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "typ": "studio_workflow_ref",
        "uid": user_id,
        "rid": str(ref_id)[:80],
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_workflow_ref_access_token(token: str) -> tuple[int, str]:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError("invalid token") from e
    if data.get("typ") != "studio_workflow_ref":
        raise ValueError("wrong token type")
    uid = data.get("uid")
    rid = data.get("rid")
    if uid is None or rid is None:
        raise ValueError("missing claims")
    return int(uid), str(rid)
