"""Клиентские и серверные события воронки активации."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.services.funnel_analytics import ALLOWED_FUNNEL_EVENTS, record_funnel_event
from app.services.workspace import workspace_owner_id

router = APIRouter(prefix="/analytics", tags=["analytics"])

_CLIENT_EVENTS = ALLOWED_FUNNEL_EVENTS - {
    "signup",
    "ws_key_saved",
    "model_created",
    "first_generation",
}


class FunnelEventIn(BaseModel):
    event: str = Field(min_length=1, max_length=64)
    meta: dict | None = None


class FunnelEventsBatchIn(BaseModel):
    events: list[FunnelEventIn] = Field(default_factory=list, max_length=20)


@router.post("/funnel")
async def post_funnel_events(
    body: FunnelEventsBatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    if user.parent_user_id is not None:
        return {"recorded": 0}
    recorded = 0
    for item in body.events:
        if item.event not in _CLIENT_EVENTS:
            continue
        await record_funnel_event(
            session,
            user=user,
            event=item.event,
            meta=item.meta,
        )
        recorded += 1
    if recorded:
        await session.commit()
    return {"recorded": recorded}
