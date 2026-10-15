"""Новый кабинет (Model Swap) — демо-доступ на /workspace/swap/.

Отдельные сущности (swap_models / swap_sessions / swap_files / swap_tasks), старые персонажи
и студия не затрагиваются. Доступ — по активной оплаченной подписке владельца пространства.

* Grok: системные инструкции живут только здесь (app.services.swap_prompts), ключ — GROK_API_KEY.
* WaveSpeed: Pro — ключ владельца из «Интеграций»; Standard/Credits — ключ платформы
  и списание кредитов только за успешный результат (как в студии).
* Картинки хранятся в data/swap/<owner_id>/, отдаются по /api/swap/files/<id> (cookie-сессия).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import BACKEND_DIR, settings
from app.db.models import SwapFile, SwapModel, SwapSession, SwapTask, User
from app.db.session import get_session
from app.services.admin_access import user_is_platform_admin
from app.services.billing_plan import is_pro_plan
from app.services.credit_units import usd_to_credits
from app.services.credits import ensure_can_consume_credits, record_usage
from app.services.crypto_secret import decrypt_secret
from app.services.entitlements import public_subscription_status, subscription_is_paid_active
from app.services.studio_keys import load_owner_studio_billing
from app.services.swap_prompts import SYSTEMS, build_system
from app.services.wavespeed_client import wavespeed_upload_image_bytes
from app.services.workspace import resolve_billing_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/swap", tags=["swap"])

FILE_PREFIX = "swapfile:"
URL_PREFIX = "/api/swap/files/"
_DATA_URL_RE = re.compile(r"^data:(image/[a-z0-9.+-]+);base64,(.*)$", re.IGNORECASE | re.DOTALL)
_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/webp": "webp", "image/gif": "gif", "image/avif": "avif"}

WS_MODELS = {
    "sd": "/api/v3/bytedance/seedream-v5.0-pro/edit",
    "gpt": "/api/v3/openai/gpt-image-2.5-sunburst/edit",
}
WS_MAX_IMAGES = {"sd": 10, "gpt": 16}
PRESETS: dict[str, dict[str, dict[str, str]]] = {
    "test": {"sd": {"resolution": "1.5k"}, "gpt": {"quality": "medium", "resolution": "1k"}},
    "final": {"sd": {"resolution": "2k"}, "gpt": {"quality": "high", "resolution": "2k"}},
}
SD_PRICE = {"1k": 0.045, "1.5k": 0.045, "2k": 0.09}
GPT_PRICE = {
    "low": {"1k": 0.025, "2k": 0.035, "4k": 0.045},
    "medium": {"1k": 0.039, "2k": 0.055, "4k": 0.085},
    "high": {"1k": 0.105, "2k": 0.165, "4k": 0.285},
}
AR_OK = {"1:1", "1:2", "2:1", "1:3", "3:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "9:21", "21:9"}


# ---------------------------------------------------------------- доступ


async def _access_info(session: AsyncSession, user: User) -> dict[str, Any]:
    billing = await resolve_billing_user(session, user)
    sub, _llm, ws, plan, balance, _demo = await load_owner_studio_billing(session, billing.id)
    admin = user_is_platform_admin(user)
    paid = subscription_is_paid_active(sub)
    enabled = bool(settings.swap_demo_enabled)
    allowed = enabled and (admin or paid or not settings.swap_demo_require_paid)
    if is_pro_plan(plan):
        ws_mode = "own"
        ws_ready = bool(ws and (ws.api_key_encrypted or "").strip())
    else:
        ws_mode = "platform"
        ws_ready = bool((settings.wavespeed_platform_api_key or "").strip())
    reason = None
    if not enabled:
        reason = "disabled"
    elif not allowed:
        reason = "subscription"
    return {
        "enabled": enabled,
        "allowed": allowed,
        "reason": reason,
        "is_admin": admin,
        "plan": plan,
        "subscription_status": public_subscription_status(sub),
        "ws_mode": ws_mode,
        "ws_ready": ws_ready,
        "grok_ready": bool((settings.grok_api_key or "").strip()),
        "credits_balance": balance,
        "charges_credits": ws_mode == "platform",
        "markup_usd": float(settings.studio_operation_markup_usd or 0),
        "owner_id": billing.id,
        "email": user.email,
    }


async def _require(session: AsyncSession, user: User) -> tuple[User, dict[str, Any]]:
    info = await _access_info(session, user)
    if not info["enabled"]:
        raise HTTPException(status_code=404, detail="Новый кабинет выключен")
    if not info["allowed"]:
        raise HTTPException(
            status_code=403,
            detail="Демо нового кабинета доступно на активной подписке. Оформите тариф в разделе «Тариф и баланс».",
        )
    billing = await resolve_billing_user(session, user)
    return billing, info


@router.get("/access")
async def swap_access(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    info = await _access_info(session, user)
    info.pop("owner_id", None)
    return info


# ---------------------------------------------------------------- файлы


def _storage_root() -> Path:
    p = Path(settings.swap_storage_dir)
    if not p.is_absolute():
        p = BACKEND_DIR / p
    return p


async def _save_bytes(session: AsyncSession, owner_id: int, data: bytes, mime: str) -> str:
    if not data:
        raise HTTPException(status_code=400, detail="Пустая картинка")
    if len(data) > settings.swap_max_image_bytes:
        raise HTTPException(status_code=413, detail="Картинка слишком большая")
    mime = (mime or "image/jpeg").lower()
    if mime not in _EXT:
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый формат: {mime}")
    digest = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(
        select(SwapFile).where(SwapFile.owner_id == owner_id, SwapFile.sha256 == digest)
    )
    if existing is not None and (_storage_root() / existing.rel_path).is_file():
        return existing.id
    fid = uuid.uuid4().hex
    rel = f"{owner_id}/{fid}.{_EXT[mime]}"
    path = _storage_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    session.add(SwapFile(id=fid, owner_id=owner_id, sha256=digest, mime=mime, size=len(data), rel_path=rel))
    await session.flush()
    return fid


async def _save_data_url(session: AsyncSession, owner_id: int, s: str) -> str:
    m = _DATA_URL_RE.match(s)
    if not m:
        raise HTTPException(status_code=400, detail="Битая картинка (data URL)")
    try:
        data = base64.b64decode(m.group(2), validate=False)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(status_code=400, detail="Битая картинка (base64)") from e
    return await _save_bytes(session, owner_id, data, m.group(1))


def _file_id_from_ref(s: str) -> str | None:
    if s.startswith(FILE_PREFIX):
        return s[len(FILE_PREFIX):]
    if s.startswith(URL_PREFIX):
        return s[len(URL_PREFIX):].split("?")[0].split("/")[0]
    return None


async def _owned_file(session: AsyncSession, owner_id: int, fid: str) -> SwapFile:
    row = await session.get(SwapFile, fid)
    if row is None or row.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return row


async def _ingest(session: AsyncSession, owner_id: int, obj: Any) -> Any:
    """data:-картинки → файлы; ссылки на наши файлы → swapfile:<id>."""
    if isinstance(obj, str):
        if obj.startswith("data:image/") and len(obj) > 64:
            return FILE_PREFIX + await _save_data_url(session, owner_id, obj)
        fid = _file_id_from_ref(obj)
        if fid and re.fullmatch(r"[0-9a-f]{32}", fid):
            return FILE_PREFIX + fid
        return obj
    if isinstance(obj, list):
        return [await _ingest(session, owner_id, x) for x in obj]
    if isinstance(obj, dict):
        return {k: await _ingest(session, owner_id, v) for k, v in obj.items()}
    return obj


def _export(obj: Any) -> Any:
    if isinstance(obj, str):
        return URL_PREFIX + obj[len(FILE_PREFIX):] if obj.startswith(FILE_PREFIX) else obj
    if isinstance(obj, list):
        return [_export(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _export(v) for k, v in obj.items()}
    return obj


@router.get("/files/{fid}")
async def swap_file(
    fid: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    billing = await resolve_billing_user(session, user)
    row = await _owned_file(session, billing.id, fid)
    path = _storage_root() / row.rel_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, media_type=row.mime, headers={"Cache-Control": "private, max-age=31536000, immutable"})


# ---------------------------------------------------------------- модели и сессии


class DocIn(BaseModel):
    doc: dict[str, Any]


def _load_doc(raw: str | None) -> dict[str, Any]:
    try:
        d = json.loads(raw or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def _check_id(doc_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", doc_id or ""):
        raise HTTPException(status_code=400, detail="Неверный id")
    return doc_id


@router.get("/models")
async def swap_models_list(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    billing, _ = await _require(session, user)
    rows = (await session.scalars(select(SwapModel).where(SwapModel.owner_id == billing.id).order_by(SwapModel.created_at))).all()
    return [_export(_load_doc(r.doc)) for r in rows]


@router.put("/models/{model_id}")
async def swap_models_put(
    model_id: str, body: DocIn, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    billing, _ = await _require(session, user)
    _check_id(model_id)
    doc = await _ingest(session, billing.id, body.doc)
    doc["id"] = model_id
    row = await session.get(SwapModel, model_id)
    if row is not None and row.owner_id != billing.id:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    if row is None:
        row = SwapModel(id=model_id, owner_id=billing.id)
        session.add(row)
    row.name = str(doc.get("name") or "")[:200]
    row.doc = json.dumps(doc, ensure_ascii=False)
    await session.commit()
    return {"doc": _export(doc)}


@router.delete("/models/{model_id}")
async def swap_models_delete(
    model_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    billing, _ = await _require(session, user)
    await session.execute(delete(SwapModel).where(SwapModel.id == _check_id(model_id), SwapModel.owner_id == billing.id))
    await session.commit()
    return {"ok": True}


@router.get("/sessions")
async def swap_sessions_list(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    billing, _ = await _require(session, user)
    rows = (
        await session.scalars(
            select(SwapSession).where(SwapSession.owner_id == billing.id).order_by(SwapSession.updated_at.desc()).limit(500)
        )
    ).all()
    return [_export(_load_doc(r.doc)) for r in rows]


@router.get("/sessions/{sid}")
async def swap_sessions_get(sid: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    billing, _ = await _require(session, user)
    row = await session.get(SwapSession, _check_id(sid))
    if row is None or row.owner_id != billing.id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return _export(_load_doc(row.doc))


@router.put("/sessions/{sid}")
async def swap_sessions_put(
    sid: str, body: DocIn, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    billing, _ = await _require(session, user)
    _check_id(sid)
    doc = await _ingest(session, billing.id, body.doc)
    doc["id"] = sid
    row = await session.get(SwapSession, sid)
    if row is not None and row.owner_id != billing.id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    if row is None:
        row = SwapSession(id=sid, owner_id=billing.id)
        session.add(row)
    row.title = str(doc.get("title") or "")[:200]
    row.model_id = str(doc.get("modelId") or "")[:32] or None
    row.doc = json.dumps(doc, ensure_ascii=False)
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"doc": _export(doc)}


@router.delete("/sessions/{sid}")
async def swap_sessions_delete(sid: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    billing, _ = await _require(session, user)
    await session.execute(delete(SwapSession).where(SwapSession.id == _check_id(sid), SwapSession.owner_id == billing.id))
    await session.commit()
    return {"ok": True}


@router.delete("/sessions")
async def swap_sessions_clear(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    billing, _ = await _require(session, user)
    await session.execute(delete(SwapSession).where(SwapSession.owner_id == billing.id))
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------- Grok


class GrokIn(BaseModel):
    task: str
    input: list[dict[str, Any]] = Field(default_factory=list)
    rules: str | None = None


async def _file_as_data_url(session: AsyncSession, owner_id: int, fid: str) -> str:
    row = await _owned_file(session, owner_id, fid)
    data = (_storage_root() / row.rel_path).read_bytes()
    return f"data:{row.mime};base64,{base64.b64encode(data).decode()}"


async def _clean_input(session: AsyncSession, owner_id: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in items[:40]:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            raise HTTPException(status_code=400, detail="Неверная роль сообщения")
        content = msg.get("content")
        if isinstance(content, str):
            out.append({"role": role, "content": content[:60000]})
            continue
        if not isinstance(content, list):
            raise HTTPException(status_code=400, detail="Неверный формат сообщения")
        parts: list[dict[str, Any]] = []
        for p in content[:60]:
            t = p.get("type")
            if t == "input_text":
                parts.append({"type": "input_text", "text": str(p.get("text") or "")[:60000]})
            elif t == "input_image":
                u = str(p.get("image_url") or "")
                fid = _file_id_from_ref(u)
                if fid:
                    u = await _file_as_data_url(session, owner_id, fid)
                elif not (u.startswith("data:image/") or u.startswith("https://")):
                    raise HTTPException(status_code=400, detail="Неверная картинка")
                parts.append({"type": "input_image", "image_url": u, "detail": "high"})
        out.append({"role": role, "content": parts})
    return out


def _response_text(j: dict[str, Any]) -> str:
    text = j.get("output_text") or ""
    if not text and isinstance(j.get("output"), list):
        for it in j["output"]:
            for c in it.get("content") or []:
                if c.get("type") in ("output_text", "text"):
                    text += c.get("text") or ""
    if not text and j.get("choices"):
        text = (j["choices"][0].get("message") or {}).get("content") or ""
    return text


@router.post("/grok")
async def swap_grok(body: GrokIn, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    billing, info = await _require(session, user)
    if body.task not in SYSTEMS:
        raise HTTPException(status_code=400, detail="Неизвестная задача")
    key = (settings.grok_api_key or "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="Grok временно недоступен. Обратитесь к администратору.")
    payload = {
        "model": settings.swap_grok_model,
        "store": False,
        "input": [{"role": "system", "content": build_system(body.task, body.rules)}, *await _clean_input(session, billing.id, body.input)],
    }
    base = (settings.grok_base_url or "https://api.x.ai/v1").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=settings.swap_grok_timeout_seconds) as c:
            r = await c.post(f"{base}/responses", headers={"Authorization": f"Bearer {key}"}, json=payload)
    except httpx.HTTPError as e:
        log.warning("swap grok network error: %s", e)
        raise HTTPException(status_code=502, detail="Grok не ответил, попробуйте ещё раз") from e
    try:
        j = r.json()
    except ValueError:
        j = {}
    if r.status_code >= 400:
        msg = str((j.get("error") or {}).get("message") if isinstance(j.get("error"), dict) else j.get("error") or r.text[:300])
        log.warning("swap grok %s: %s", r.status_code, msg)
        raise HTTPException(status_code=502, detail=f"Grok: {msg}")
    text = _response_text(j)
    if not text:
        raise HTTPException(status_code=502, detail="Grok вернул пустой ответ")
    if body.task != "ping":
        await record_usage(session, user, billing, f"swap_grok_{body.task}", 0, {"model": settings.swap_grok_model})
        await session.commit()
    return {"text": text}


# ---------------------------------------------------------------- WaveSpeed


async def _ws_key(session: AsyncSession, owner_id: int, mode: str | None = None) -> tuple[str, str]:
    _sub, _llm, ws, plan, _bal, _demo = await load_owner_studio_billing(session, owner_id)
    mode = mode or ("own" if is_pro_plan(plan) else "platform")
    if mode == "own":
        if not ws or not (ws.api_key_encrypted or "").strip():
            raise HTTPException(status_code=400, detail="WS_KEY_MISSING: подключите свой ключ WaveSpeed в разделе «Интеграции» старого кабинета.")
        try:
            return decrypt_secret(ws.api_key_encrypted), mode
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Не удалось расшифровать ключ WaveSpeed") from e
    key = (settings.wavespeed_platform_api_key or "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="Генерация временно недоступна. Обратитесь к администратору.")
    return key, mode


def _ws_base() -> str:
    return (settings.wavespeed_api_base or "https://api.wavespeed.ai").rstrip("/")


def _ws_error_text(j: Any, fallback: str) -> str:
    if isinstance(j, dict):
        for v in (j.get("message"), (j.get("data") or {}).get("error") if isinstance(j.get("data"), dict) else None, j.get("error")):
            if v:
                return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return fallback


def _price_usd(gen: str, preset: str, n_images: int) -> float:
    p = PRESETS[preset][gen]
    extra = max(0, n_images - 1)
    if gen == "sd":
        return SD_PRICE[p["resolution"]] + 0.003 * extra
    return GPT_PRICE[p["quality"]][p["resolution"]] + 0.015 * extra


class UploadIn(BaseModel):
    src: str


@router.post("/ws/upload")
async def swap_ws_upload(body: UploadIn, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    billing, _ = await _require(session, user)
    src = body.src or ""
    if src.startswith("https://"):
        return {"url": src}
    if src.startswith("data:image/"):
        fid = await _save_data_url(session, billing.id, src)
    else:
        fid = _file_id_from_ref(src)
        if not fid:
            raise HTTPException(status_code=400, detail="Неверная картинка")
    row = await _owned_file(session, billing.id, fid)
    now = datetime.now(timezone.utc)
    if row.ws_url and row.ws_url_at and now - row.ws_url_at.replace(tzinfo=row.ws_url_at.tzinfo or timezone.utc) < timedelta(days=5):
        await session.commit()
        return {"url": row.ws_url}
    key, _mode = await _ws_key(session, billing.id)
    data = (_storage_root() / row.rel_path).read_bytes()
    try:
        url = await wavespeed_upload_image_bytes(api_key=key, data=data, filename=f"{row.id}.{_EXT.get(row.mime, 'jpg')}", content_type=row.mime)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    row.ws_url, row.ws_url_at = url, now
    await session.commit()
    return {"url": url}


class SubmitIn(BaseModel):
    gen: str
    preset: str
    prompt: str
    images: list[str]
    aspect_ratio: str | None = None


@router.post("/ws/submit")
async def swap_ws_submit(body: SubmitIn, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    billing, _info = await _require(session, user)
    if body.gen not in WS_MODELS or body.preset not in PRESETS:
        raise HTTPException(status_code=400, detail="Неверный генератор или пресет")
    prompt = (body.prompt or "").strip()
    if not prompt or len(prompt) > 8000:
        raise HTTPException(status_code=400, detail="Пустой или слишком длинный промпт")
    images = [u for u in body.images if isinstance(u, str) and u.startswith("https://")]
    if not images or len(images) != len(body.images) or len(images) > WS_MAX_IMAGES[body.gen]:
        raise HTTPException(status_code=400, detail="Картинки должны быть загружены в WaveSpeed (1–%d шт.)" % WS_MAX_IMAGES[body.gen])
    key, mode = await _ws_key(session, billing.id)
    price = _price_usd(body.gen, body.preset, len(images))
    credits = usd_to_credits(price) if mode == "platform" else 0
    if credits:
        await ensure_can_consume_credits(session, user, credits)
    payload: dict[str, Any] = {"prompt": prompt, "images": images, "output_format": "png", **PRESETS[body.preset][body.gen]}
    if body.gen == "sd":
        payload["prompt_optimization_mode"] = "standard"
    if body.aspect_ratio in AR_OK:
        payload["aspect_ratio"] = body.aspect_ratio
    try:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(_ws_base() + WS_MODELS[body.gen], headers={"Authorization": f"Bearer {key}"}, json=payload)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="WaveSpeed не ответил, попробуйте ещё раз") from e
    try:
        j = r.json()
    except ValueError:
        j = {}
    code = j.get("code") if isinstance(j, dict) else None
    if r.status_code >= 400 or (code not in (None, 200)):
        msg = _ws_error_text(j, r.text[:300] or f"HTTP {r.status_code}")
        status = 402 if r.status_code == 402 or re.search(r"insufficient|balance|credit", msg, re.I) else 400 if r.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=f"WaveSpeed: {msg}")
    data = j.get("data") if isinstance(j.get("data"), dict) else j
    task_id = str((data or {}).get("id") or "")
    if not task_id:
        raise HTTPException(status_code=502, detail="WaveSpeed не вернул id задачи")
    session.add(SwapTask(
        id=task_id, owner_id=billing.id, actor_id=user.id, gen=body.gen, preset=body.preset, key_mode=mode,
        n_images=len(images), price_usd=price, credits=credits, status="created",
    ))
    await session.commit()
    return {"id": task_id, "price_usd": price, "credits": credits, "mode": mode}


def _first_output(outputs: Any) -> str | None:
    if isinstance(outputs, list):
        for o in outputs:
            if isinstance(o, str) and o.startswith("http"):
                return o
            if isinstance(o, dict):
                for k in ("url", "uri"):
                    if isinstance(o.get(k), str):
                        return o[k]
    return None


def _task_out(t: SwapTask) -> dict[str, Any]:
    return {
        "status": t.status,
        "outputs": [URL_PREFIX + t.output_file_id] if t.output_file_id else [],
        "error": t.error,
        "timings": {"inference": t.inference_ms} if t.inference_ms else {},
        "credits": t.credits if t.charged else 0,
    }


@router.get("/ws/task/{task_id}")
async def swap_ws_task(task_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    billing, _ = await _require(session, user)
    t = await session.scalar(select(SwapTask).where(SwapTask.id == task_id).with_for_update())
    if t is None or t.owner_id != billing.id:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if t.status in ("completed", "failed"):
        return _task_out(t)
    key, _mode = await _ws_key(session, billing.id, t.key_mode)
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(f"{_ws_base()}/api/v3/predictions/{task_id}/result", headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError:
        await session.rollback()
        return {"status": "processing", "transient": "network"}
    try:
        j = r.json()
    except ValueError:
        j = {}
    if r.status_code >= 500 or r.status_code == 429:
        await session.rollback()
        return {"status": "processing", "transient": f"HTTP {r.status_code}"}
    if r.status_code >= 400 or (isinstance(j, dict) and j.get("code") not in (None, 200)):
        t.status, t.error = "failed", _ws_error_text(j, f"HTTP {r.status_code}")
        await session.commit()
        return _task_out(t)
    d = j.get("data") if isinstance(j.get("data"), dict) else j
    st = str(d.get("status") or "").lower()
    if st == "completed":
        url = _first_output(d.get("outputs"))
        if not url:
            t.status, t.error = "failed", "WaveSpeed: задача завершилась без картинки"
            await session.commit()
            return _task_out(t)
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as c:
                img = await c.get(url)
            img.raise_for_status()
        except httpx.HTTPError:
            await session.rollback()
            return {"status": "processing", "transient": "download"}
        mime = (img.headers.get("content-type") or "image/png").split(";")[0].strip().lower()
        if mime not in _EXT:
            mime = "image/png"
        t.output_file_id = await _save_bytes(session, billing.id, img.content, mime)
        t.inference_ms = int(((d.get("timings") or {}).get("inference")) or 0) or None
        t.status = "completed"
        if t.key_mode == "platform" and t.credits > 0 and not t.charged:
            actor = user
            try:
                await record_usage(session, actor, billing, "swap_generation", t.credits,
                                   {"task": t.id, "gen": t.gen, "preset": t.preset, "usd": t.price_usd})
                t.charged = True
            except HTTPException:
                log.warning("swap: не удалось списать %s кредитов за %s (недостаточно)", t.credits, t.id)
        await session.commit()
        return _task_out(t)
    if st in ("failed", "cancelled", "canceled", "timeout", "deleted", "error"):
        t.status, t.error = "failed", _ws_error_text({"error": d.get("error")}, f"WaveSpeed: задача {st}")
        await session.commit()
        return _task_out(t)
    await session.rollback()
    return {"status": "processing"}
