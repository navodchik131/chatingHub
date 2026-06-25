"""Очередь и отправка email-кампаний из админки."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    EmailCampaign,
    EmailCampaignRecipient,
    EmailCampaignRecipientStatus,
    EmailCampaignStatus,
    User,
)
from app.db.session import SessionLocal
from app.services.admin_segments import resolve_segment_owner_ids
from app.services.email_service import render_email_body, send_email

log = logging.getLogger(__name__)


@dataclass
class _CampaignSendCtx:
    id: int
    subject: str
    body_html: str
    body_text: str | None


async def queue_campaign(
    session: AsyncSession,
    campaign: EmailCampaign,
) -> EmailCampaign:
    owner_ids = await resolve_segment_owner_ids(session, campaign.segment)
    if not owner_ids:
        campaign.status = EmailCampaignStatus.failed
        campaign.error_message = "Сегмент пуст"
        campaign.completed_at = datetime.now(timezone.utc)
        return campaign

    users = (
        (await session.execute(select(User).where(User.id.in_(owner_ids))))
        .scalars()
        .all()
    )
    by_id = {u.id: u for u in users}

    recipients: list[EmailCampaignRecipient] = []
    skipped = 0
    for oid in owner_ids:
        u = by_id.get(oid)
        if not u:
            continue
        if u.email_marketing_opt_out or not u.is_active:
            skipped += 1
            recipients.append(
                EmailCampaignRecipient(
                    campaign_id=campaign.id,
                    user_id=u.id,
                    email=u.email,
                    status=EmailCampaignRecipientStatus.skipped,
                    error_message="opt_out" if u.email_marketing_opt_out else "inactive",
                )
            )
        else:
            recipients.append(
                EmailCampaignRecipient(
                    campaign_id=campaign.id,
                    user_id=u.id,
                    email=u.email,
                    status=EmailCampaignRecipientStatus.pending,
                )
            )

    session.add_all(recipients)
    campaign.recipient_count = len(recipients)
    campaign.skipped_count = skipped
    campaign.status = EmailCampaignStatus.queued
    campaign.started_at = datetime.now(timezone.utc)
    await session.flush()
    return campaign


async def process_email_campaigns_once() -> int:
    """Отправляет одну пачку pending-писем. Возвращает число успешно отправленных."""
    if not settings.smtp_configured:
        return 0

    batch_size = settings.email_campaign_batch_size
    sent_total = 0

    async with SessionLocal() as session:
        campaign = (
            await session.execute(
                select(EmailCampaign)
                .where(
                    EmailCampaign.status.in_(
                        (EmailCampaignStatus.queued, EmailCampaignStatus.sending)
                    )
                )
                .order_by(EmailCampaign.id.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if not campaign:
            return 0

        if campaign.status == EmailCampaignStatus.queued:
            campaign.status = EmailCampaignStatus.sending

        pending = (
            (
                await session.execute(
                    select(EmailCampaignRecipient)
                    .where(
                        EmailCampaignRecipient.campaign_id == campaign.id,
                        EmailCampaignRecipient.status
                        == EmailCampaignRecipientStatus.pending,
                    )
                    .order_by(EmailCampaignRecipient.id.asc())
                    .limit(batch_size)
                )
            )
            .scalars()
            .all()
        )
        if not pending:
            campaign.status = EmailCampaignStatus.completed
            campaign.completed_at = datetime.now(timezone.utc)
            await session.commit()
            return 0

        ctx = _CampaignSendCtx(
            id=campaign.id,
            subject=campaign.subject,
            body_html=campaign.body_html,
            body_text=campaign.body_text,
        )
        pending_ids = [p.id for p in pending]
        pending_emails = [p.email for p in pending]
        await session.commit()

    for rec_id, email in zip(pending_ids, pending_emails, strict=True):
        try:
            html = render_email_body(ctx.body_html, email=email)
            text = (
                render_email_body(ctx.body_text, email=email)
                if ctx.body_text
                else None
            )
            await send_email(
                to_email=email,
                subject=ctx.subject,
                body_html=html,
                body_text=text,
            )
            async with SessionLocal() as session:
                rec = await session.get(EmailCampaignRecipient, rec_id)
                camp = await session.get(EmailCampaign, ctx.id)
                if rec and camp:
                    rec.status = EmailCampaignRecipientStatus.sent
                    rec.sent_at = datetime.now(timezone.utc)
                    camp.sent_count += 1
                    await session.commit()
            sent_total += 1
        except Exception as e:
            log.exception("Campaign %s failed for %s", ctx.id, email)
            async with SessionLocal() as session:
                rec = await session.get(EmailCampaignRecipient, rec_id)
                camp = await session.get(EmailCampaign, ctx.id)
                if rec and camp:
                    rec.status = EmailCampaignRecipientStatus.failed
                    rec.error_message = str(e)[:2000]
                    camp.failed_count += 1
                    await session.commit()

    async with SessionLocal() as session:
        remaining = int(
            await session.scalar(
                select(func.count(EmailCampaignRecipient.id)).where(
                    EmailCampaignRecipient.campaign_id == ctx.id,
                    EmailCampaignRecipient.status
                    == EmailCampaignRecipientStatus.pending,
                )
            )
            or 0
        )
        if remaining == 0:
            camp = await session.get(EmailCampaign, ctx.id)
            if camp and camp.status != EmailCampaignStatus.completed:
                camp.status = EmailCampaignStatus.completed
                camp.completed_at = datetime.now(timezone.utc)
                await session.commit()

    return sent_total


async def email_campaign_worker_loop() -> None:
    await asyncio.sleep(15)
    delay = max(0.5, settings.email_campaign_batch_delay_seconds)
    while True:
        try:
            processed = await process_email_campaigns_once()
            if processed == 0:
                await asyncio.sleep(max(5.0, delay * 2))
            else:
                await asyncio.sleep(delay)
        except Exception:
            log.exception("Email campaign worker failed")
            await asyncio.sleep(30)
