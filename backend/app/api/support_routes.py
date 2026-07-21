"""Пользовательские маршруты обращений в поддержку."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.db.models import SupportTicket, SupportTicketStatus, User
from app.db.session import get_session
from app.schemas import (
    SupportTicketCreateIn,
    SupportTicketListItemOut,
    SupportTicketOut,
    SupportTicketReplyOut,
)
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
    return [
        SupportTicketListItemOut(
            id=r.id,
            type=r.type,
            subject=r.subject,
            status=r.status.value,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


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
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
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
    return _ticket_out(row)
