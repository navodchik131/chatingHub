"""Admin API обращений в поддержку."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_platform_admin
from app.db.models import SupportTicket, SupportTicketReply, SupportTicketStatus, User
from app.db.session import get_session
from app.schemas import (
    AdminSupportTicketListItemOut,
    AdminSupportTicketOut,
    AdminSupportTicketReplyIn,
    AdminSupportTicketStatusPatchIn,
    SupportTicketReplyOut,
)
from app.services.support_push import notify_support_reply_to_user

router = APIRouter(prefix="/admin/tickets", tags=["admin"])


def _admin_ticket_out(row: SupportTicket, user_email: str) -> AdminSupportTicketOut:
    return AdminSupportTicketOut(
        id=row.id,
        user_id=row.user_id,
        user_email=user_email,
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


def _admin_list_item(row: SupportTicket, user_email: str) -> AdminSupportTicketListItemOut:
    return AdminSupportTicketListItemOut(
        id=row.id,
        user_id=row.user_id,
        user_email=user_email,
        type=row.type,
        subject=row.subject,
        status=row.status.value,
        user_has_unread=bool(row.user_has_unread),
        admin_has_unread=bool(row.admin_has_unread),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _load_admin_ticket(
    session: AsyncSession, ticket_id: int
) -> tuple[SupportTicket, str]:
    stmt = (
        select(SupportTicket, User.email)
        .join(User, User.id == SupportTicket.user_id)
        .where(SupportTicket.id == ticket_id)
        .options(selectinload(SupportTicket.replies))
    )
    row = (await session.execute(stmt)).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    ticket, email = row[0], row[1]
    return ticket, email


@router.get("/unread-count")
async def admin_support_unread_count(
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    stmt = (
        select(func.count())
        .select_from(SupportTicket)
        .where(SupportTicket.admin_has_unread.is_(True))
    )
    count = int((await session.execute(stmt)).scalar_one() or 0)
    return {"count": count}


@router.get("", response_model=list[AdminSupportTicketListItemOut])
async def admin_list_support_tickets(
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AdminSupportTicketListItemOut]:
    stmt = (
        select(SupportTicket, User.email)
        .join(User, User.id == SupportTicket.user_id)
        .order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
        .limit(limit)
    )
    if status:
        key = status.strip().lower()
        try:
            st = SupportTicketStatus(key)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Некорректный status") from e
        stmt = stmt.where(SupportTicket.status == st)
    rows = (await session.execute(stmt)).all()
    return [_admin_list_item(ticket, email) for ticket, email in rows]


@router.get("/{ticket_id}", response_model=AdminSupportTicketOut)
async def admin_get_support_ticket(
    ticket_id: int,
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminSupportTicketOut:
    ticket, email = await _load_admin_ticket(session, ticket_id)
    if ticket.admin_has_unread:
        ticket.admin_has_unread = False
        await session.commit()
        await session.refresh(ticket, attribute_names=["replies", "updated_at"])
    return _admin_ticket_out(ticket, email)


@router.post("/{ticket_id}/reply", response_model=AdminSupportTicketOut)
async def admin_reply_support_ticket(
    ticket_id: int,
    body: AdminSupportTicketReplyIn,
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminSupportTicketOut:
    ticket, email = await _load_admin_ticket(session, ticket_id)
    msg = body.message.strip()
    reply = SupportTicketReply(
        ticket_id=ticket.id,
        is_staff=True,
        message=msg,
    )
    session.add(reply)
    if ticket.status == SupportTicketStatus.submitted:
        ticket.status = SupportTicketStatus.in_review
    elif ticket.status == SupportTicketStatus.in_review:
        ticket.status = SupportTicketStatus.answered
    ticket.user_has_unread = True
    await session.commit()
    await session.refresh(ticket, attribute_names=["replies", "updated_at"])
    await notify_support_reply_to_user(
        ticket.user_id,
        ticket_id=ticket.id,
        subject=ticket.subject,
        preview=msg,
    )
    return _admin_ticket_out(ticket, email)


@router.patch("/{ticket_id}/status", response_model=AdminSupportTicketOut)
async def admin_patch_support_ticket_status(
    ticket_id: int,
    body: AdminSupportTicketStatusPatchIn,
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminSupportTicketOut:
    ticket, email = await _load_admin_ticket(session, ticket_id)
    ticket.status = SupportTicketStatus(body.status)
    await session.commit()
    await session.refresh(ticket, attribute_names=["replies", "updated_at"])
    return _admin_ticket_out(ticket, email)
