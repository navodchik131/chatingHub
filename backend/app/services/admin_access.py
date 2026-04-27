from __future__ import annotations

from app.config import settings
from app.db.models import User


def _admin_email_allowlist() -> set[str]:
    raw = (settings.admin_emails or "").strip()
    if not raw:
        return set()
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def user_is_platform_admin(user: User) -> bool:
    """Доступ к админ-API: только владелец пространства (без parent)."""
    if user.parent_user_id is not None:
        return False
    if user.is_platform_admin:
        return True
    return user.email.lower() in _admin_email_allowlist()
