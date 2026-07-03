"""KPI чатеров: исходящие сообщения, диалоги, рейтинги AI, Tribute."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BotResponseEvent,
    BotResponseEventStatus,
    Conversation,
    Message,
    MessageDirection,
    User,
)
from app.services.tribute_earnings import aggregate_tribute_earnings
from app.services.workspace import is_workspace_owner, workspace_owner_id
from app.services.workspace_model_access import member_allowed_studio_model_ids


def _period_bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(to_date, time.max, tzinfo=timezone.utc)
    return start, end


def _apply_model_filter(stmt, allowed_models: set[int] | None):
    if allowed_models is None:
        return stmt
    if not allowed_models:
        return stmt.where(Conversation.id == -1)
    return stmt.where(Conversation.studio_model_id.in_(allowed_models))


async def _outbound_stats_for_actor(
    session: AsyncSession,
    *,
    owner_id: int,
    actor_id: int,
    allowed_models: set[int] | None,
    start: datetime,
    end: datetime,
) -> tuple[int, int]:
    base = (
        select(Message.id, Message.conversation_id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == owner_id,
            Message.direction == MessageDirection.outbound,
            Message.sender_user_id == actor_id,
            Message.created_at >= start,
            Message.created_at <= end,
        )
    )
    base = _apply_model_filter(base, allowed_models)
    rows = list((await session.execute(base)).all())
    if not rows:
        return 0, 0
    return len(rows), len({r[1] for r in rows})


async def _companion_ratings_for_actor(
    session: AsyncSession,
    *,
    owner_id: int,
    actor_id: int,
    allowed_models: set[int] | None,
    start: datetime,
    end: datetime,
) -> tuple[int, int]:
    stmt = (
        select(BotResponseEvent.operator_rating)
        .join(Message, BotResponseEvent.outbound_message_id == Message.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == owner_id,
            Message.sender_user_id == actor_id,
            BotResponseEvent.status == BotResponseEventStatus.sent,
            BotResponseEvent.sent_at.isnot(None),
            BotResponseEvent.sent_at >= start,
            BotResponseEvent.sent_at <= end,
            BotResponseEvent.operator_rating.isnot(None),
        )
    )
    stmt = _apply_model_filter(stmt, allowed_models)
    ratings = [int(r or 0) for r in (await session.execute(stmt)).scalars().all()]
    pos = sum(1 for r in ratings if r > 0)
    neg = sum(1 for r in ratings if r < 0)
    return pos, neg


async def stats_row_for_user(
    session: AsyncSession,
    *,
    actor: User,
    owner_id: int,
    from_date: date,
    to_date: date,
) -> dict:
    start, end = _period_bounds(from_date, to_date)
    allowed = await member_allowed_studio_model_ids(session, actor)
    outbound, convs = await _outbound_stats_for_actor(
        session,
        owner_id=owner_id,
        actor_id=actor.id,
        allowed_models=allowed,
        start=start,
        end=end,
    )
    pos, neg = await _companion_ratings_for_actor(
        session,
        owner_id=owner_id,
        actor_id=actor.id,
        allowed_models=allowed,
        start=start,
        end=end,
    )
    tribute = await aggregate_tribute_earnings(
        session,
        viewer=actor,
        from_date=from_date,
        to_date=to_date,
    )
    return {
        "user_id": actor.id,
        "member_login": actor.member_login or "",
        "is_active": actor.is_active,
        "outbound_messages": outbound,
        "conversations_replied": convs,
        "companion_ratings_positive": pos,
        "companion_ratings_negative": neg,
        "tribute_display_minor": int(tribute.get("display_minor") or 0),
        "tribute_gross_minor": int(tribute.get("gross_minor") or 0),
        "tribute_currency": str(tribute.get("currency") or "USD"),
        "tribute_share_percent": int(tribute.get("chatter_share_percent") or 0),
        "tribute_event_count": int(tribute.get("event_count") or 0),
    }


async def aggregate_chatter_stats_summary(
    session: AsyncSession,
    *,
    viewer: User,
    from_date: date,
    to_date: date,
) -> dict:
    if to_date < from_date:
        from_date, to_date = to_date, from_date

    owner_id = workspace_owner_id(viewer)
    self_row = await stats_row_for_user(
        session,
        actor=viewer,
        owner_id=owner_id,
        from_date=from_date,
        to_date=to_date,
    )

    members: list[dict] | None = None
    if is_workspace_owner(viewer):
        stmt = (
            select(User)
            .where(User.parent_user_id == owner_id)
            .order_by(User.member_login.asc(), User.id.asc())
        )
        team = list((await session.execute(stmt)).scalars().all())
        members = []
        for m in team:
            members.append(
                await stats_row_for_user(
                    session,
                    actor=m,
                    owner_id=owner_id,
                    from_date=from_date,
                    to_date=to_date,
                )
            )

    return {
        "from_date": from_date,
        "to_date": to_date,
        "is_owner": is_workspace_owner(viewer),
        "self": self_row,
        "members": members,
    }
