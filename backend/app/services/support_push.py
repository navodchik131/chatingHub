"""Push-уведомления по обращениям в поддержку."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.config import settings
from app.db.repo import list_mobile_push_tokens, list_platform_admin_user_ids, list_push_subscriptions
from app.db.session import SessionLocal
from app.services.expo_push import EXPO_PUSH_URL
from app.services.webpush import _send_sync

log = logging.getLogger(__name__)


async def _send_web_push(owner_user_id: int, *, title: str, body: str, url: str) -> None:
    if not settings.web_push_configured:
        return
    payload = json.dumps({"title": title, "body": body, "url": url}, ensure_ascii=False)
    async with SessionLocal() as session:
        subs = await list_push_subscriptions(session, owner_user_id)
    for s in subs:
        info: dict[str, Any] = {
            "endpoint": s.endpoint,
            "keys": {"p256dh": s.p256dh, "auth": s.auth},
        }
        code = await asyncio.to_thread(_send_sync, info, payload)
        if code is not None and code >= 400:
            log.debug("support webpush HTTP %s for user=%s", code, owner_user_id)


async def _send_mobile_push(
    owner_user_id: int,
    *,
    title: str,
    body: str,
    data: dict[str, Any],
) -> None:
    import httpx

    from app.db.repo import delete_mobile_push_token_by_id

    async with SessionLocal() as session:
        tokens = await list_mobile_push_tokens(session, owner_user_id)
    if not tokens:
        return

    messages = [
        {
            "to": t.expo_token,
            "title": title[:200],
            "body": body[:2000],
            "sound": "default",
            "priority": "high",
            "data": data,
        }
        for t in tokens
    ]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(EXPO_PUSH_URL, json=messages)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as e:
        log.warning("support expo push: %s", e)
        return

    data_list = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data_list, list):
        return
    for item, token_row in zip(data_list, tokens, strict=False):
        if not isinstance(item, dict):
            continue
        if item.get("status") == "error":
            err = str((item.get("details") or {}).get("error") or "")
            if err in ("DeviceNotRegistered", "InvalidCredentials"):
                async with SessionLocal() as session:
                    await delete_mobile_push_token_by_id(session, token_row.id)
                    await session.commit()


async def notify_support_reply_to_user(
    owner_user_id: int,
    *,
    ticket_id: int,
    subject: str,
    preview: str,
) -> None:
    base = settings.public_app_url.rstrip("/")
    title = "Ответ поддержки"
    body = f"{subject.strip()}: {(preview or '').strip()[:120]}"
    url = f"{base}/workspace/support?ticket={ticket_id}"
    await _send_web_push(owner_user_id, title=title, body=body, url=url)
    await _send_mobile_push(
        owner_user_id,
        title=title,
        body=body,
        data={"ticket_id": ticket_id, "kind": "support_reply"},
    )


async def notify_admins_new_support(
    *,
    ticket_id: int,
    subject: str,
    user_email: str,
) -> None:
    async with SessionLocal() as session:
        admin_ids = await list_platform_admin_user_ids(session)
    if not admin_ids:
        return

    base = settings.public_app_url.rstrip("/")
    title = "Новое обращение"
    body = f"{user_email}: {subject.strip()[:120]}"
    url = f"{base}/admin?tickets={ticket_id}"
    for admin_id in admin_ids:
        await _send_web_push(admin_id, title=title, body=body, url=url)
        await _send_mobile_push(
            admin_id,
            title=title,
            body=body,
            data={"ticket_id": ticket_id, "kind": "support_new"},
        )
