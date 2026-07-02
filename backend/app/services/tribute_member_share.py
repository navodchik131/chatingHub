"""Доля Tribute для участников workspace."""

from __future__ import annotations

from app.config import settings
from app.db.models import User
from app.services.workspace import is_workspace_owner


def default_tribute_share_percent() -> int:
    return int(settings.tribute_chatter_share_percent)


def resolve_member_tribute_share_percent(user: User) -> int:
    if is_workspace_owner(user):
        return 100
    if user.tribute_share_percent is not None:
        return max(0, min(100, int(user.tribute_share_percent)))
    return default_tribute_share_percent()


def member_tribute_share_ratio(user: User) -> float:
    return resolve_member_tribute_share_percent(user) / 100.0
