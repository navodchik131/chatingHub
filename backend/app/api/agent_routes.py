"""Persona Studio в кабинете model-mate (демо, /workspace/agent/).

Сама студия крутится отдельным контейнером `agent` (код Persona Studio в режиме «хостинг»).
Здесь — только то, что принадлежит инфраструктуре model-mate:

* POST /api/agent/session — кто пришёл (cookie/Bearer пользователя, переданные студией) → владелец
  пространства, тариф, баланс и ключи (Grok — платформы; WaveSpeed — платформы на Standard/Credits,
  свой из «Интеграций» на Pro);
* POST /api/agent/check — хватит ли кредитов на операцию;
* POST /api/agent/charge — списать фактическую стоимость операции.

Цена в кредитах = ceil(себестоимость $ × AGENT_CREDIT_MULTIPLIER × 100) (1 кредит = 1 цент).
Grok считается по токенам из ответа xAI (цены — AGENT_GROK_PRICES_JSON), WaveSpeed — по цене кадра/видео.
Все /session, /check, /charge требуют заголовок X-Internal-Token = AGENT_INTERNAL_TOKEN (только из сети Docker).
"""

from __future__ import annotations

import hmac
import json
import logging
import math
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.db.models import CreditAccount, UsageEvent, User
from app.db.session import get_session
from app.services.admin_access import user_is_platform_admin
from app.services.billing_plan import is_pro_plan
from app.services.credit_units import CREDITS_PER_USD
from app.services.credits import _lock_credit_account
from app.services.crypto_secret import decrypt_secret
from app.services.entitlements import public_subscription_status, subscription_is_paid_active
from app.services.studio_keys import load_owner_studio_billing
from app.services.workspace import resolve_billing_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

# $ за 1 млн токенов: (вход, вход из кэша, выход). Ключ — префикс имени модели, берётся самый длинный.
DEFAULT_GROK_PRICES: dict[str, tuple[float, float, float]] = {
    "grok-4": (3.0, 0.75, 15.0),
    "grok-4-fast": (0.2, 0.05, 0.5),
    "grok-4-1-fast": (0.2, 0.05, 0.5),
    "grok-4.5": (2.0, 0.5, 6.0),
    "grok-4.6": (2.0, 0.5, 6.0),
    "grok-4.7": (2.0, 0.5, 6.0),
}
FALLBACK_GROK_PRICE = (3.0, 0.75, 15.0)   # неизвестная модель — считаем по самой дорогой


# ---------------------------------------------------------------- цены


def grok_prices() -> dict[str, tuple[float, float, float]]:
    out = dict(DEFAULT_GROK_PRICES)
    raw = (settings.agent_grok_prices_json or "").strip()
    if raw:
        try:
            for k, v in json.loads(raw).items():
                out[str(k)] = (float(v[0]), float(v[1]), float(v[2]))
        except (ValueError, TypeError, IndexError, AttributeError):
            log.warning("AGENT_GROK_PRICES_JSON не разобран — беру цены по умолчанию")
    return out


def grok_usd(model: str | None, usage: dict[str, Any] | None) -> tuple[float, dict[str, Any]]:
    """Себестоимость одного ответа Grok по usage из xAI. Возвращает ($, детали для журнала)."""
    u = usage or {}
    prompt = int(u.get("prompt_tokens") or 0)
    completion = int(u.get("completion_tokens") or 0)
    total = int(u.get("total_tokens") or 0)
    cached = int(((u.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0)
    reasoning = int(((u.get("completion_tokens_details") or {}).get("reasoning_tokens")) or 0)
    # у xAI рассуждения могут не входить в completion_tokens, но всегда входят в total_tokens
    out = max(completion, total - prompt, completion + reasoning if total == 0 else 0)
    name = (model or "").lower()
    table = grok_prices()
    key = max((k for k in table if name.startswith(k)), key=len, default=None)
    p_in, p_cache, p_out = table[key] if key else FALLBACK_GROK_PRICE
    cached = min(cached, prompt)
    by_tokens = ((prompt - cached) * p_in + cached * p_cache + out * p_out) / 1_000_000
    ticks = u.get("cost_in_usd_ticks")
    by_ticks = float(ticks) / 1e10 if isinstance(ticks, (int, float)) and ticks > 0 else 0.0
    # если xAI прислал свою стоимость — берём большее из двух (защита от устаревшей таблицы цен)
    usd = max(by_tokens, by_ticks)
    return usd, {"model": model, "price_key": key, "prompt": prompt, "cached": cached, "out": out,
                 "usd_tokens": round(by_tokens, 6), "usd_ticks": round(by_ticks, 6) if by_ticks else None}


def usd_to_agent_credits(usd: float) -> int:
    if usd <= 0:
        return 0
    return max(1, math.ceil(usd * float(settings.agent_credit_multiplier) * CREDITS_PER_USD - 1e-9))


# ---------------------------------------------------------------- доступ


def _internal(token: str | None) -> None:
    want = (settings.agent_internal_token or "").strip()
    if not want:
        raise HTTPException(status_code=503, detail="Новый кабинет не настроен (AGENT_INTERNAL_TOKEN)")
    if not token or not hmac.compare_digest(token.strip(), want):
        raise HTTPException(status_code=403, detail="bad internal token")


async def access_info(session: AsyncSession, user: User) -> dict[str, Any]:
    billing = await resolve_billing_user(session, user)
    sub, _llm, ws, plan, balance, _demo = await load_owner_studio_billing(session, billing.id)
    admin = user_is_platform_admin(user)
    paid = subscription_is_paid_active(sub)
    enabled = bool(settings.agent_demo_enabled)
    # всё платное списывается по факту, поэтому пускаем и без подписки, если есть кредиты
    allowed = enabled and (admin or paid or balance > 0 or not settings.agent_demo_require_paid)
    own = is_pro_plan(plan)
    reason = None if allowed else ("disabled" if not enabled else "subscription")
    return {
        "enabled": enabled,
        "allowed": allowed,
        "reason": reason,
        "is_admin": admin,
        "plan": plan,
        "subscription_status": public_subscription_status(sub),
        "ws_mode": "own" if own else "platform",
        "ws_ready": bool(ws and (ws.api_key_encrypted or "").strip()) if own else bool((settings.wavespeed_platform_api_key or "").strip()),
        "grok_ready": bool((settings.grok_api_key or "").strip()),
        "balance": balance,
        "multiplier": float(settings.agent_credit_multiplier),
        "billing_id": billing.id,
        "_ws_row": ws,
    }


@router.get("/access")
async def agent_access(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Для кнопки «Новый кабинет · агент» в старом кабинете."""
    info = await access_info(session, user)
    return {k: v for k, v in info.items() if not k.startswith("_") and k != "billing_id"} | {"url": settings.agent_public_path}


@router.post("/session")
async def agent_session(
    x_internal_token: str | None = Header(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _internal(x_internal_token)
    info = await access_info(session, user)
    if not info["allowed"]:
        msg = ("Новый кабинет выключен" if info["reason"] == "disabled" else
               "Демо нового кабинета доступно на активной подписке или с кредитами на балансе. "
               "Оформите тариф или пополните баланс в разделе «Тариф и баланс».")
        raise HTTPException(status_code=403, detail={"message": msg, "reason": info["reason"]})
    ws_key = ""
    if info["ws_mode"] == "own":
        row = info["_ws_row"]
        if row is not None and (row.api_key_encrypted or "").strip():
            try:
                ws_key = decrypt_secret(row.api_key_encrypted)
            except ValueError:
                log.warning("agent: не расшифровал ключ WaveSpeed владельца %s", info["billing_id"])
    else:
        ws_key = (settings.wavespeed_platform_api_key or "").strip()
    return {
        "owner_id": info["billing_id"],
        "actor_id": user.id,
        "plan": info["plan"],
        "ws_mode": info["ws_mode"],
        "balance": info["balance"],
        "multiplier": info["multiplier"],
        "grok_model": settings.agent_grok_model,
        "billing_url": settings.agent_billing_url,
        "is_admin": info["is_admin"],
        "xai_key": (settings.grok_api_key or "").strip(),
        "wavespeed_key": ws_key,
    }


# ---------------------------------------------------------------- кредиты


class CheckIn(BaseModel):
    owner_id: int
    usd: float = Field(ge=0, le=1000)


@router.post("/check")
async def agent_check(body: CheckIn, x_internal_token: str | None = Header(default=None),
                      session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    _internal(x_internal_token)
    acc = await session.scalar(select(CreditAccount).where(CreditAccount.user_id == body.owner_id))
    balance = int(acc.balance) if acc is not None else 0
    need = usd_to_agent_credits(body.usd)
    return {"ok": balance >= need, "need": need, "balance": balance}


class ChargeIn(BaseModel):
    owner_id: int
    actor_id: int | None = None
    kind: str = Field(min_length=3, max_length=60)
    usd: float = Field(default=0.0, ge=0, le=1000)
    usage: dict[str, Any] | None = None
    model: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


@router.post("/charge")
async def agent_charge(body: ChargeIn, x_internal_token: str | None = Header(default=None),
                       session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Списать фактическую стоимость. Работа уже выполнена, поэтому при нехватке списываем остаток
    и пишем недостачу в журнал (перед запуском студия проверяет баланс через /check)."""
    _internal(x_internal_token)
    if not body.kind.startswith("agent_"):
        raise HTTPException(status_code=400, detail="kind должен начинаться с agent_")
    owner = await session.get(User, body.owner_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="владелец не найден")
    usd = float(body.usd)
    meta: dict[str, Any] = {k: v for k, v in list(body.meta.items())[:20]}
    if body.usage is not None:
        usd, detail = grok_usd(body.model, body.usage)
        meta["grok"] = detail
    credits = usd_to_agent_credits(usd)
    acc = await _lock_credit_account(session, owner.id)
    take = min(credits, max(0, int(acc.balance)))
    acc.balance -= take
    meta.update(usd=round(usd, 6), credits=credits, multiplier=float(settings.agent_credit_multiplier))
    if take < credits:
        meta["shortfall"] = credits - take
        log.warning("agent: недостача %s кр. у владельца %s (%s)", credits - take, owner.id, body.kind)
    if body.actor_id and body.actor_id != owner.id:
        meta["actor_user_id"] = body.actor_id
    session.add(UsageEvent(user_id=owner.id, kind=body.kind, credits_delta=-take,
                           meta=json.dumps(meta, ensure_ascii=False, default=str)))
    await session.commit()
    return {"credits": take, "need": credits, "usd": round(usd, 6), "balance": int(acc.balance)}
