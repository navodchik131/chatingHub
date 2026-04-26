"""Отправка Web Push (VAPID) при входящих сообщениях."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.config import settings
from app.db.repo import delete_push_subscription_by_id, list_push_subscriptions
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


def _send_sync(subscription: dict[str, Any], payload: str) -> int | None:
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=settings.vapid_private_key.strip(),
            vapid_claims={"sub": settings.vapid_sub.strip()},
            ttl=86400,
        )
        return None
    except WebPushException as e:
        if getattr(e, "response", None) is not None:
            return e.response.status_code
        log.warning("webpush: %s", e)
        return 500
    except Exception as e:
        log.warning("webpush: %s", e)
        return 500


async def notify_inbound_message(
    owner_user_id: int,
    *,
    conversation_id: int,
    title: str,
    body: str,
) -> None:
    if not settings.web_push_configured:
        return
    text = (body or "")[:2000]
    title_t = (title or "Сообщение")[:200]
    base = settings.public_app_url.rstrip("/")
    target_url = f"{base}/?conv={conversation_id}"
    payload = json.dumps(
        {"title": title_t, "body": text, "url": target_url},
        ensure_ascii=False,
    )
    async with SessionLocal() as session:
        subs = await list_push_subscriptions(session, owner_user_id)
    if not subs:
        return
    for s in subs:
        info: dict[str, Any] = {
            "endpoint": s.endpoint,
            "keys": {"p256dh": s.p256dh, "auth": s.auth},
        }
        code = await asyncio.to_thread(_send_sync, info, payload)
        if code in (404, 410):
            async with SessionLocal() as s2:
                await delete_push_subscription_by_id(s2, s.id)
                await s2.commit()
        elif code is not None and code >= 400:
            log.debug("webpush HTTP %s for subscription id=%s", code, s.id)
