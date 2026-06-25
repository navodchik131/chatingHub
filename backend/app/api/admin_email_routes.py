"""API email-рассылок в админке."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_platform_admin
from app.config import settings
from app.db.models import EmailCampaign, EmailCampaignStatus, User
from app.db.session import get_session
from app.schemas import (
    AdminEmailCampaignCreateIn,
    AdminEmailCampaignOut,
    AdminEmailConfigOut,
    AdminEmailSegmentPreviewOut,
    AdminEmailSendTestIn,
    AdminEmailTemplateOut,
)
from app.services.admin_segments import (
    EMAIL_CAMPAIGN_SEGMENTS,
    SEGMENT_TITLES,
    count_email_eligible_recipients,
)
from app.services.email_campaigns import queue_campaign
from app.services.email_service import check_smtp_connectivity, render_email_body, send_email
from app.services.email_templates import EMAIL_TEMPLATES, list_email_templates

router = APIRouter(tags=["admin-email"])


def _campaign_out(c: EmailCampaign) -> AdminEmailCampaignOut:
    return AdminEmailCampaignOut(
        id=c.id,
        segment=c.segment,
        segment_title=SEGMENT_TITLES.get(c.segment, c.segment),
        subject=c.subject,
        body_html=c.body_html,
        body_text=c.body_text,
        status=c.status.value,
        recipient_count=c.recipient_count,
        sent_count=c.sent_count,
        failed_count=c.failed_count,
        skipped_count=c.skipped_count,
        error_message=c.error_message,
        created_at=c.created_at,
        started_at=c.started_at,
        completed_at=c.completed_at,
    )


@router.get("/admin/email/config", response_model=AdminEmailConfigOut)
async def admin_email_config(
    _: User = Depends(get_platform_admin),
) -> AdminEmailConfigOut:
    segments = [
        {"id": sid, "title": SEGMENT_TITLES[sid]}
        for sid in sorted(EMAIL_CAMPAIGN_SEGMENTS)
    ]
    return AdminEmailConfigOut(
        smtp_configured=settings.smtp_configured,
        from_email=settings.smtp_from_email or None,
        from_name=settings.smtp_from_name or None,
        segments=segments,
    )


@router.get("/admin/email/smtp-check")
async def admin_email_smtp_check(
    _: User = Depends(get_platform_admin),
) -> dict:
    if not settings.smtp_configured:
        raise HTTPException(status_code=503, detail="SMTP не настроен")
    return check_smtp_connectivity()


@router.get("/admin/email/templates", response_model=list[AdminEmailTemplateOut])
async def admin_email_templates(
    _: User = Depends(get_platform_admin),
) -> list[AdminEmailTemplateOut]:
    return [AdminEmailTemplateOut(**t) for t in list_email_templates()]


@router.get("/admin/email/segment-preview", response_model=AdminEmailSegmentPreviewOut)
async def admin_email_segment_preview(
    segment: str = Query(..., min_length=1, max_length=64),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminEmailSegmentPreviewOut:
    key = segment.strip().lower()
    if key not in EMAIL_CAMPAIGN_SEGMENTS:
        raise HTTPException(status_code=400, detail="Неизвестный сегмент")
    counts = await count_email_eligible_recipients(session, key)
    return AdminEmailSegmentPreviewOut(
        segment=key,
        title=SEGMENT_TITLES[key],
        **counts,
    )


@router.get("/admin/email/campaigns", response_model=list[AdminEmailCampaignOut])
async def admin_email_campaigns_list(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AdminEmailCampaignOut]:
    rows = (
        (
            await session.execute(
                select(EmailCampaign)
                .order_by(EmailCampaign.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_campaign_out(c) for c in rows]


@router.post("/admin/email/campaigns", response_model=AdminEmailCampaignOut)
async def admin_email_campaign_create(
    body: AdminEmailCampaignCreateIn,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_platform_admin),
) -> AdminEmailCampaignOut:
    if not settings.smtp_configured:
        raise HTTPException(
            status_code=503,
            detail="SMTP не настроен. Укажите SMTP_HOST и SMTP_FROM_EMAIL в .env",
        )
    segment = body.segment.strip().lower()
    if segment not in EMAIL_CAMPAIGN_SEGMENTS:
        raise HTTPException(status_code=400, detail="Неизвестный сегмент")

    subject = (body.subject or "").strip()
    body_html = (body.body_html or "").strip()
    body_text = (body.body_text or "").strip() or None

    if body.template_id:
        tpl = EMAIL_TEMPLATES.get(body.template_id.strip())
        if not tpl:
            raise HTTPException(status_code=400, detail="Неизвестный шаблон")
        if not subject:
            subject = tpl["subject"]
        if body.use_template_body:
            body_html = tpl["body_html"]
            body_text = tpl.get("body_text") or None

    if not subject or not body_html:
        raise HTTPException(status_code=400, detail="Тема и HTML-текст обязательны")

    campaign = EmailCampaign(
        segment=segment,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        status=EmailCampaignStatus.draft,
        created_by_user_id=admin.id,
    )
    session.add(campaign)
    await session.flush()

    if body.send_now:
        await queue_campaign(session, campaign)

    await session.commit()
    await session.refresh(campaign)
    return _campaign_out(campaign)


@router.post("/admin/email/campaigns/{campaign_id}/send", response_model=AdminEmailCampaignOut)
async def admin_email_campaign_send(
    campaign_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminEmailCampaignOut:
    if not settings.smtp_configured:
        raise HTTPException(status_code=503, detail="SMTP не настроен")
    campaign = await session.get(EmailCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    if campaign.status not in (EmailCampaignStatus.draft,):
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя отправить кампанию в статусе {campaign.status.value}",
        )
    await queue_campaign(session, campaign)
    await session.commit()
    await session.refresh(campaign)
    return _campaign_out(campaign)


@router.post("/admin/email/test")
async def admin_email_send_test(
    body: AdminEmailSendTestIn,
    _: User = Depends(get_platform_admin),
) -> dict:
    if not settings.smtp_configured:
        raise HTTPException(status_code=503, detail="SMTP не настроен")
    to_email = body.to_email.strip().lower()
    subject = body.subject.strip()
    body_html = body.body_html.strip()
    if not to_email or not subject or not body_html:
        raise HTTPException(status_code=400, detail="Email, тема и HTML обязательны")
    try:
        await send_email(
            to_email=to_email,
            subject=subject,
            body_html=render_email_body(body_html, email=to_email),
            body_text=(
                render_email_body(body.body_text, email=to_email)
                if body.body_text
                else None
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"ok": True}
