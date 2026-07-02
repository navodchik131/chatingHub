"""Tribute: URL webhook и доступ к подключению."""

from __future__ import annotations

from app.config import settings
from app.db.models import TributeConnection


def tribute_webhook_url_for_connection(conn: TributeConnection) -> str:
    base = settings.public_app_url.rstrip("/")
    return f"{base}/api/webhooks/tribute/{conn.webhook_secret}"
