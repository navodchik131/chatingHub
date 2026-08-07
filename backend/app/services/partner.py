"""Партнёрская программа: ссылки, атрибуция, комиссии, аналитика."""

from __future__ import annotations

import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import PartnerCommission, PartnerLink, Subscription, User
from app.services.billing_plan import normalize_billing_plan
from app.services.plan_catalog import plan_display_name
from app.services.referral import REFERRER_REWARD_KIND

log = logging.getLogger(__name__)

PARTNER_COMMISSION_KIND = "partner_commission"
PARTNER_BASE_LINK_TAG = "_base"
VALID_DESTS = frozenset({"home", "pricing", "studio", "chats"})

DEST_PATHS = {
    "home": "/",
    "pricing": "/pricing",
    "studio": "/workspace/images",
    "chats": "/workspace/dialogs",
}
PUBLIC_DESTS = frozenset({"home", "pricing"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _kopecks_from_rub(amount_rub: int | Decimal) -> int:
    rub = Decimal(str(amount_rub)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(rub * 100)


def _rub_from_kopecks(kopecks: int) -> Decimal:
    return (Decimal(kopecks) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_partner_tag(raw: str) -> str:
    tag = (raw or "").strip().lower()
    tag = re.sub(r"[^a-z0-9_-]+", "-", tag)
    tag = re.sub(r"-{2,}", "-", tag).strip("-")
    return tag[:48]


def slugify_partner_base(email: str) -> str:
    base = (email or "").split("@")[0].lower()
    base = re.sub(r"[^a-z0-9]", "", base)[:20]
    return base if len(base) >= 3 else "partner"


def normalize_partner_slug(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", (raw or "").strip().lower())[:32]
    if len(slug) < 3:
        raise ValueError("Партнёрский slug: от 3 до 32 символов, только латиница и цифры")
    return slug


async def ensure_partner_slug(session: AsyncSession, owner: User) -> str:
    slug = (getattr(owner, "partner_slug", None) or "").strip().lower()
    if slug:
        return slug
    base = slugify_partner_base(owner.email)
    for i in range(24):
        candidate = base if i == 0 else f"{base}{i}"
        dup = await session.scalar(select(User.id).where(User.partner_slug == candidate))
        if not dup:
            owner.partner_slug = candidate
            await session.flush()
            return candidate
    fallback = f"p{secrets.token_hex(4)}"
    owner.partner_slug = fallback
    await session.flush()
    return fallback


async def find_partner_by_slug(session: AsyncSession, slug: str) -> User | None:
    s = (slug or "").strip().lower()
    if not s:
        return None
    stmt = select(User).where(
        User.partner_slug == s,
        User.is_partner.is_(True),
        User.parent_user_id.is_(None),
        User.is_active.is_(True),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def ensure_partner_base_link(session: AsyncSession, partner_id: int) -> PartnerLink:
    link = await get_partner_link(session, partner_id=partner_id, tag=PARTNER_BASE_LINK_TAG)
    if link is not None:
        return link
    link = PartnerLink(
        partner_user_id=partner_id,
        tag=PARTNER_BASE_LINK_TAG,
        note="",
        dest="home",
        clicks=0,
    )
    session.add(link)
    await session.flush()
    return link


async def get_partner_link(
    session: AsyncSession, *, partner_id: int, tag: str
) -> PartnerLink | None:
    t = normalize_partner_tag(tag)
    if not t:
        return None
    stmt = select(PartnerLink).where(
        PartnerLink.partner_user_id == partner_id,
        PartnerLink.tag == t,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def apply_partner_referral_on_signup(
    session: AsyncSession,
    *,
    new_owner: User,
    partner_slug: str | None,
    source_tag: str | None = None,
) -> int | None:
    slug = (partner_slug or "").strip().lower()
    if not slug:
        return None
    partner = await find_partner_by_slug(session, slug)
    if partner is None or partner.id == new_owner.id:
        return None

    new_owner.referred_by_user_id = partner.id
    new_owner.partner_discount_eligible = True

    tag = normalize_partner_tag(source_tag or "")
    if tag:
        new_owner.referral_source_tag = tag
        link = await get_partner_link(session, partner_id=partner.id, tag=tag)
        if link is not None:
            new_owner.referred_by_partner_link_id = link.id
    else:
        base_link = await ensure_partner_base_link(session, partner.id)
        new_owner.referred_by_partner_link_id = base_link.id

    await session.flush()
    return partner.id


async def record_partner_link_click(
    session: AsyncSession,
    *,
    partner: User,
    source_tag: str | None,
) -> None:
    tag = normalize_partner_tag(source_tag or "")
    if tag:
        link = await get_partner_link(session, partner_id=partner.id, tag=tag)
    else:
        link = await ensure_partner_base_link(session, partner.id)
    if link is None:
        return
    link.clicks = int(link.clicks or 0) + 1
    await session.flush()


async def increment_partner_link_registration(
    session: AsyncSession, *, user: User
) -> None:
    link_id = getattr(user, "referred_by_partner_link_id", None)
    if not link_id:
        return
    link = await session.get(PartnerLink, link_id)
    if link is None:
        return
    # regs tracked via referred users count per link — no separate column needed


def partner_public_base_link(slug: str) -> str:
    base = settings.public_app_url.rstrip("/")
    return f"{base}/r/{slug}"


def partner_link_url(slug: str, *, tag: str | None = None, dest: str = "home") -> str:
    url = partner_public_base_link(slug)
    params: list[str] = []
    if tag:
        params.append(f"src={normalize_partner_tag(tag)}")
    d = dest if dest in VALID_DESTS else "home"
    if d != "home":
        params.append(f"to={d}")
    if params:
        url += "?" + "&".join(params)
    return url


def partner_login_redirect_url(partner: User, *, source_tag: str | None, dest: str) -> str:
    base = settings.public_app_url.rstrip("/")
    slug = (partner.partner_slug or "").strip()
    params = [f"pref={slug}"]
    tag = normalize_partner_tag(source_tag or "")
    if tag:
        params.append(f"src={tag}")
    d = dest if dest in VALID_DESTS else "home"
    if d != "home":
        params.append(f"to={d}")
    path = DEST_PATHS.get(d, "/")
    params.append(f"next={path}")
    return f"{base}/login?{'&'.join(params)}"


def partner_public_redirect_url(partner: User, *, source_tag: str | None, dest: str) -> str:
    """Публичные страницы — сразу на лендинг/тарифы с pref/src для атрибуции при регистрации."""
    base = settings.public_app_url.rstrip("/")
    slug = (partner.partner_slug or "").strip()
    d = dest if dest in PUBLIC_DESTS else "home"
    path = DEST_PATHS.get(d, "/")
    params = [f"pref={slug}"]
    tag = normalize_partner_tag(source_tag or "")
    if tag:
        params.append(f"src={tag}")
    return f"{base}{path}?{'&'.join(params)}"


def partner_redirect_url(partner: User, *, source_tag: str | None, dest: str) -> str:
    d = dest if dest in VALID_DESTS else "home"
    if d in PUBLIC_DESTS:
        return partner_public_redirect_url(partner, source_tag=source_tag, dest=d)
    return partner_login_redirect_url(partner, source_tag=source_tag, dest=d)


async def partner_first_payment_discount_rub(
    session: AsyncSession,
    owner: User,
    amount_rub: int,
) -> tuple[int, int]:
    """Возвращает (сумма_к_оплате, скидка_руб)."""
    if getattr(owner, "partner_discount_used", False):
        return amount_rub, 0
    if not getattr(owner, "partner_discount_eligible", False):
        return amount_rub, 0
    if not owner.referred_by_user_id:
        return amount_rub, 0
    referrer = await session.get(User, owner.referred_by_user_id)
    if referrer is None or not getattr(referrer, "is_partner", False):
        return amount_rub, 0
    pct = max(0, int(settings.partner_referred_first_payment_discount_percent))
    if pct <= 0:
        return amount_rub, 0
    discount = int(Decimal(amount_rub) * Decimal(pct) / Decimal(100))
    discount = min(discount, amount_rub)
    return amount_rub - discount, discount


async def mark_partner_discount_used(session: AsyncSession, owner_id: int) -> None:
    owner = await session.get(User, owner_id)
    if owner is None or owner.partner_discount_used:
        return
    if not owner.partner_discount_eligible:
        return
    owner.partner_discount_used = True
    await session.flush()


def commission_kopecks_from_payment_rub(amount_rub: int | Decimal) -> int:
    pct = max(0, int(settings.partner_commission_percent))
    rub = Decimal(str(amount_rub)) * Decimal(pct) / Decimal(100)
    return _kopecks_from_rub(rub)


def partner_commission_available_at(payment_at: datetime) -> datetime:
    dt = payment_at if payment_at.tzinfo else payment_at.replace(tzinfo=timezone.utc)
    hold_days = max(0, int(settings.partner_payout_hold_days))
    return dt + timedelta(days=hold_days)


async def grant_partner_commission_if_needed(
    session: AsyncSession,
    referred_owner_id: int,
    *,
    payment_ref: str,
    payment_amount_rub: int | Decimal,
) -> None:
    referred = await session.get(User, referred_owner_id)
    if not referred or not referred.referred_by_user_id:
        return
    partner = await session.get(User, referred.referred_by_user_id)
    if partner is None or not getattr(partner, "is_partner", False):
        return

    ref = (payment_ref or "").strip()
    if not ref:
        return
    dup = await session.scalar(
        select(PartnerCommission.id).where(PartnerCommission.payment_ref == ref)
    )
    if dup:
        return

    paid_kopecks = _kopecks_from_rub(payment_amount_rub)
    commission_kopecks = commission_kopecks_from_payment_rub(payment_amount_rub)
    if commission_kopecks <= 0:
        return

    now = _now()
    session.add(
        PartnerCommission(
            partner_user_id=partner.id,
            referred_user_id=referred.id,
            partner_link_id=referred.referred_by_partner_link_id,
            payment_ref=ref,
            payment_amount_kopecks=paid_kopecks,
            commission_kopecks=commission_kopecks,
            status="hold",
            created_at=now,
            available_at=partner_commission_available_at(now),
        )
    )
    log.info(
        "partner commission partner=%s referred=%s kopecks=%s from_rub=%s",
        partner.id,
        referred_owner_id,
        commission_kopecks,
        payment_amount_rub,
    )


async def create_partner_link(
    session: AsyncSession,
    *,
    partner_id: int,
    tag: str,
    note: str = "",
    dest: str = "home",
) -> PartnerLink:
    t = normalize_partner_tag(tag)
    if not t:
        raise ValueError("invalid tag")
    if t == PARTNER_BASE_LINK_TAG:
        raise ValueError("reserved tag")
    d = dest if dest in VALID_DESTS else "home"
    existing = await get_partner_link(session, partner_id=partner_id, tag=t)
    if existing:
        raise ValueError("tag exists")
    row = PartnerLink(
        partner_user_id=partner_id,
        tag=t,
        note=(note or "")[:255],
        dest=d,
    )
    session.add(row)
    await session.flush()
    return row


async def _referred_users_query(partner_id: int, source_tag: str | None = None):
    stmt = select(User).where(User.referred_by_user_id == partner_id)
    if source_tag and source_tag != "all":
        stmt = stmt.where(User.referral_source_tag == normalize_partner_tag(source_tag))
    return stmt.order_by(User.created_at.desc())


async def _user_total_paid_kopecks(session: AsyncSession, user_id: int) -> int:
    from app.db.models import YookassaProcessedPayment

    # Approximate from partner commissions + yookassa — use commissions for referred users
    total = await session.scalar(
        select(func.coalesce(func.sum(PartnerCommission.payment_amount_kopecks), 0)).where(
            PartnerCommission.referred_user_id == user_id
        )
    )
    return int(total or 0)


async def _user_commission_for_partner(
    session: AsyncSession, *, partner_id: int, referred_id: int
) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(PartnerCommission.commission_kopecks), 0)).where(
            PartnerCommission.partner_user_id == partner_id,
            PartnerCommission.referred_user_id == referred_id,
        )
    )
    return int(total or 0)


def _mask_email(email: str) -> str:
    e = (email or "").strip()
    if "@" not in e:
        return e[:3] + "***" if len(e) > 3 else e
    local, domain = e.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


async def partner_referrals_list(
    session: AsyncSession,
    *,
    partner_id: int,
    source_tag: str | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = await _referred_users_query(partner_id, source_tag)
    stmt = stmt.limit(limit)
    users = (await session.execute(stmt)).scalars().all()
    out: list[dict] = []
    for u in users:
        sub = await session.scalar(select(Subscription).where(Subscription.user_id == u.id))
        bp = normalize_billing_plan(sub.billing_plan if sub else None)
        tier = sub.plan_tier if sub else "solo"
        plan = plan_display_name(bp, tier) if sub else "—"
        paid_k = await _user_total_paid_kopecks(session, u.id)
        reward_k = await _user_commission_for_partner(session, partner_id=partner_id, referred_id=u.id)
        st = "none"
        if paid_k > 0:
            st = "active"
        out.append(
            {
                "user_id": u.id,
                "email_masked": _mask_email(u.email),
                "source_tag": u.referral_source_tag or "—",
                "plan": plan,
                "joined_at": u.created_at.isoformat() if u.created_at else None,
                "paid_kopecks": paid_k,
                "reward_kopecks": reward_k,
                "status": st,
            }
        )
    return out


async def partner_analytics(session: AsyncSession, partner_id: int) -> dict:
    now = _now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    referred_total = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.referred_by_user_id == partner_id)
        )
        or 0
    )

    subscribed = int(
        await session.scalar(
            select(func.count(func.distinct(PartnerCommission.referred_user_id))).where(
                PartnerCommission.partner_user_id == partner_id
            )
        )
        or 0
    )

    earned_total = int(
        await session.scalar(
            select(func.coalesce(func.sum(PartnerCommission.commission_kopecks), 0)).where(
                PartnerCommission.partner_user_id == partner_id,
                PartnerCommission.status != "cancelled",
            )
        )
        or 0
    )

    earned_month = int(
        await session.scalar(
            select(func.coalesce(func.sum(PartnerCommission.commission_kopecks), 0)).where(
                PartnerCommission.partner_user_id == partner_id,
                PartnerCommission.created_at >= month_start,
                PartnerCommission.status != "cancelled",
            )
        )
        or 0
    )

    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    earned_prev_month = int(
        await session.scalar(
            select(func.coalesce(func.sum(PartnerCommission.commission_kopecks), 0)).where(
                PartnerCommission.partner_user_id == partner_id,
                PartnerCommission.created_at >= prev_month_start,
                PartnerCommission.created_at < month_start,
                PartnerCommission.status != "cancelled",
            )
        )
        or 0
    )

    referred_month = int(
        await session.scalar(
            select(func.count()).select_from(User).where(
                User.referred_by_user_id == partner_id,
                User.created_at >= month_start,
            )
        )
        or 0
    )

    referred_prev = int(
        await session.scalar(
            select(func.count()).select_from(User).where(
                User.referred_by_user_id == partner_id,
                User.created_at >= prev_month_start,
                User.created_at < month_start,
            )
        )
        or 0
    )

    avg_payment = 0
    if subscribed:
        total_paid = int(
            await session.scalar(
                select(func.coalesce(func.sum(PartnerCommission.payment_amount_kopecks), 0)).where(
                    PartnerCommission.partner_user_id == partner_id
                )
            )
            or 0
        )
        payments_count = int(
            await session.scalar(
                select(func.count()).select_from(PartnerCommission).where(
                    PartnerCommission.partner_user_id == partner_id
                )
            )
            or 0
        )
        if payments_count:
            avg_payment = total_paid // payments_count

    # Chart: last 8 months
    chart: list[dict] = []
    for i in range(7, -1, -1):
        m_start = (month_start - timedelta(days=1)).replace(day=1)
        for _ in range(i):
            m_start = (m_start - timedelta(days=1)).replace(day=1)
        if m_start.month == 12:
            m_end = m_start.replace(year=m_start.year + 1, month=1)
        else:
            m_end = m_start.replace(month=m_start.month + 1)
        earn = int(
            await session.scalar(
                select(func.coalesce(func.sum(PartnerCommission.commission_kopecks), 0)).where(
                    PartnerCommission.partner_user_id == partner_id,
                    PartnerCommission.created_at >= m_start,
                    PartnerCommission.created_at < m_end,
                )
            )
            or 0
        )
        regs = int(
            await session.scalar(
                select(func.count()).select_from(User).where(
                    User.referred_by_user_id == partner_id,
                    User.created_at >= m_start,
                    User.created_at < m_end,
                )
            )
            or 0
        )
        chart.append(
            {
                "month": m_start.strftime("%Y-%m"),
                "earn_kopecks": earn,
                "registrations": regs,
            }
        )

    links = (
        await session.execute(
            select(PartnerLink).where(PartnerLink.partner_user_id == partner_id).order_by(
                PartnerLink.created_at.desc()
            )
        )
    ).scalars().all()

    link_stats: list[dict] = []
    tagged_regs_sum = 0
    tagged_paid_sum = 0
    for link in links:
        if link.tag == PARTNER_BASE_LINK_TAG:
            continue
        regs = int(
            await session.scalar(
                select(func.count()).select_from(User).where(
                    User.referred_by_partner_link_id == link.id
                )
            )
            or 0
        )
        paid_users = int(
            await session.scalar(
                select(func.count(func.distinct(PartnerCommission.referred_user_id))).where(
                    PartnerCommission.partner_user_id == partner_id,
                    PartnerCommission.partner_link_id == link.id,
                )
            )
            or 0
        )
        earned = int(
            await session.scalar(
                select(func.coalesce(func.sum(PartnerCommission.commission_kopecks), 0)).where(
                    PartnerCommission.partner_user_id == partner_id,
                    PartnerCommission.partner_link_id == link.id,
                )
            )
            or 0
        )
        tagged_regs_sum += regs
        tagged_paid_sum += paid_users
        link_stats.append(
            {
                "id": link.id,
                "tag": link.tag,
                "note": link.note,
                "dest": link.dest,
                "clicks": int(link.clicks or 0),
                "registrations": regs,
                "paying_users": paid_users,
                "earned_kopecks": earned,
            }
        )

    base_link_row = await ensure_partner_base_link(session, partner_id)
    base_regs = max(0, referred_total - tagged_regs_sum)
    base_paid = max(0, subscribed - tagged_paid_sum)
    base_link_stats = {
        "clicks": int(base_link_row.clicks or 0),
        "registrations": base_regs,
        "paying_users": base_paid,
    }

    top_clients: list[dict] = []
    top_rows = (
        await session.execute(
            select(
                PartnerCommission.referred_user_id,
                func.sum(PartnerCommission.payment_amount_kopecks).label("paid"),
                func.sum(PartnerCommission.commission_kopecks).label("reward"),
            )
            .where(PartnerCommission.partner_user_id == partner_id)
            .group_by(PartnerCommission.referred_user_id)
            .order_by(func.sum(PartnerCommission.payment_amount_kopecks).desc())
            .limit(5)
        )
    ).all()
    for row in top_rows:
        u = await session.get(User, row.referred_user_id)
        if not u:
            continue
        sub = await session.scalar(select(Subscription).where(Subscription.user_id == u.id))
        bp = normalize_billing_plan(sub.billing_plan if sub else None)
        tier = sub.plan_tier if sub else "solo"
        top_clients.append(
            {
                "email_masked": _mask_email(u.email),
                "plan": plan_display_name(bp, tier),
                "paid_kopecks": int(row.paid or 0),
                "reward_kopecks": int(row.reward or 0),
            }
        )

    recent_events: list[dict] = []
    comm_rows = (
        await session.execute(
            select(PartnerCommission)
            .where(PartnerCommission.partner_user_id == partner_id)
            .order_by(PartnerCommission.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    for c in comm_rows:
        u = await session.get(User, c.referred_user_id)
        recent_events.append(
            {
                "kind": "commission",
                "text": f"Комиссия · {_mask_email(u.email if u else '')}",
                "amount_kopecks": c.commission_kopecks,
                "status": c.status,
                "at": c.created_at.isoformat() if c.created_at else None,
            }
        )

    total_clicks = int(base_link_row.clicks or 0) + sum(int(l["clicks"]) for l in link_stats)

    return {
        "referred_total": referred_total,
        "subscribed_count": subscribed,
        "earned_total_kopecks": earned_total,
        "earned_month_kopecks": earned_month,
        "earned_prev_month_kopecks": earned_prev_month,
        "referred_month": referred_month,
        "referred_prev_month": referred_prev,
        "avg_payment_kopecks": avg_payment,
        "total_clicks": total_clicks,
        "base_link": base_link_stats,
        "chart": chart,
        "links": link_stats,
        "top_clients": top_clients,
        "recent_events": recent_events,
        "commission_percent": int(settings.partner_commission_percent),
        "discount_percent": int(settings.partner_referred_first_payment_discount_percent),
        "payout_hold_days": int(settings.partner_payout_hold_days),
        "payout_min_kopecks": _kopecks_from_rub(settings.partner_payout_min_rub),
    }


def partner_public_dict() -> dict:
    return {
        "commission_percent": int(settings.partner_commission_percent),
        "referred_discount_percent": int(settings.partner_referred_first_payment_discount_percent),
        "payout_hold_days": int(settings.partner_payout_hold_days),
        "payout_min_rub": int(settings.partner_payout_min_rub),
    }
