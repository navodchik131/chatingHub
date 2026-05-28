from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    key = (settings.fernet_key or "").strip()
    if not key:
        raise RuntimeError(
            "FERNET_KEY не задан. Сгенерируйте: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except ValueError as e:
        raise RuntimeError(
            "FERNET_KEY неверного формата (нужен ключ Fernet из generate_key). "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        ) from e


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("invalid encrypted secret") from e
