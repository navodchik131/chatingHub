from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.db.models import User
from app.db.repo import delete_push_subscription, upsert_push_subscription
from app.db.session import get_session
from app.schemas import PushSubscribeIn, PushUnsubscribeIn
from app.services.workspace import PERM_CHAT, assert_permission, workspace_owner_id

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key")
async def vapid_public_key() -> dict[str, str]:
    if not settings.web_push_configured:
        raise HTTPException(status_code=503, detail="web push not configured on server")
    return {"public_key": settings.vapid_public_key.strip()}


@router.post("/subscribe")
async def push_subscribe(
    body: PushSubscribeIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
) -> dict[str, str]:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    p256 = body.keys.get("p256dh", "")
    auth = body.keys.get("auth", "")
    if len(p256) < 4 or len(auth) < 4:
        raise HTTPException(status_code=400, detail="invalid key material")
    await upsert_push_subscription(
        session,
        oid,
        body.endpoint,
        p256,
        auth,
        (user_agent or "")[:512] or None,
    )
    await session.commit()
    return {"ok": "true"}


@router.post("/unsubscribe")
async def push_unsubscribe(
    body: PushUnsubscribeIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    await delete_push_subscription(session, oid, body.endpoint)
    await session.commit()
    return {"ok": "true"}
