"""Пользовательские маршруты обращений в поддержку."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.db.models import SupportTicket, SupportTicketReply, SupportTicketStatus, User
from app.db.session import get_session
from app.schemas import (
    SupportTicketCreateIn,
    SupportTicketListItemOut,
    SupportTicketOut,
    SupportTicketReplyOut,
    SupportTicketUserReplyIn,
)
from app.services.support_push import notify_admins_new_support, notify_support_reply_to_user
from app.services.workspace import workspace_owner_id

router = APIRouter(prefix="/support", tags=["support"])


def _ticket_out(row: SupportTicket) -> SupportTicketOut:
    return SupportTicketOut(
        id=row.id,
        type=row.type,
        subject=row.subject,
        message=row.message,
        status=row.status.value,
        created_at=row.created_at,
        updated_at=row.updated_at,
        replies=[
            SupportTicketReplyOut(
                id=r.id,
                is_staff=r.is_staff,
                message=r.message,
                created_at=r.created_at,
            )
            for r in (row.replies or [])
        ],
    )


def _list_item(row: SupportTicket) -> SupportTicketListItemOut:
    return SupportTicketListItemOut(
        id=row.id,
        type=row.type,
        subject=row.subject,
        status=row.status.value,
        user_has_unread=bool(row.user_has_unread),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/unread-count")
async def support_unread_count(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    oid = workspace_owner_id(user)
    stmt = (
        select(func.count())
        .select_from(SupportTicket)
        .where(SupportTicket.user_id == oid, SupportTicket.user_has_unread.is_(True))
    )
    count = int((await session.execute(stmt)).scalar_one() or 0)
    return {"count": count}


@router.get("/tickets", response_model=list[SupportTicketListItemOut])
async def list_support_tickets(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[SupportTicketListItemOut]:
    oid = workspace_owner_id(user)
    stmt = (
        select(SupportTicket)
        .where(SupportTicket.user_id == oid)
        .order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_list_item(r) for r in rows]


@router.post("/tickets", response_model=SupportTicketOut, status_code=201)
async def create_support_ticket(
    body: SupportTicketCreateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> SupportTicketOut:
    oid = workspace_owner_id(user)
    row = SupportTicket(
        user_id=oid,
        type=body.type.strip(),
        subject=body.subject.strip(),
        message=body.message.strip(),
        status=SupportTicketStatus.submitted,
        admin_has_unread=True,
        user_has_unread=False,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await notify_admins_new_support(
        ticket_id=row.id,
        subject=row.subject,
        user_email=user.email,
    )
    return SupportTicketOut(
        id=row.id,
        type=row.type,
        subject=row.subject,
        message=row.message,
        status=row.status.value,
        created_at=row.created_at,
        updated_at=row.updated_at,
        replies=[],
    )


@router.post("/tickets/{ticket_id}/reply", response_model=SupportTicketOut)
async def user_reply_support_ticket(
    ticket_id: int,
    body: SupportTicketUserReplyIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> SupportTicketOut:
    oid = workspace_owner_id(user)
    stmt = (
        select(SupportTicket)
        .where(SupportTicket.id == ticket_id, SupportTicket.user_id == oid)
        .options(selectinload(SupportTicket.replies))
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    if row.status == SupportTicketStatus.closed:
        raise HTTPException(status_code=400, detail="Обращение закрыто")
    msg = body.message.strip()
    session.add(
        SupportTicketReply(
            ticket_id=row.id,
            is_staff=False,
            message=msg,
        )
    )
    if row.status == SupportTicketStatus.answered:
        row.status = SupportTicketStatus.in_review
    row.admin_has_unread = True
    await session.commit()
    await session.refresh(row, attribute_names=["replies", "updated_at"])
    await notify_admins_new_support(
        ticket_id=row.id,
        subject=row.subject,
        user_email=user.email,
    )
    return _ticket_out(row)


@router.get("/tickets/{ticket_id}", response_model=SupportTicketOut)
async def get_support_ticket(
    ticket_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> SupportTicketOut:
    oid = workspace_owner_id(user)
    stmt = (
        select(SupportTicket)
        .where(SupportTicket.id == ticket_id, SupportTicket.user_id == oid)
        .options(selectinload(SupportTicket.replies))
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    if row.user_has_unread:
        row.user_has_unread = False
        await session.commit()
        await session.refresh(row, attribute_names=["replies", "updated_at"])
    return _ticket_out(row)
