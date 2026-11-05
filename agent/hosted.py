"""Режим «хостинг» для model-mate.online.

Включается переменной PS_HOSTED_API (адрес внутреннего API model-mate, например http://api:8080/api/agent).
Тогда Persona Studio:
  * не хранит ключей и не показывает настройки ключей/промптов — вход, тариф и ключи даёт model-mate;
  * каждый чат принадлежит владельцу пространства (owner), чужие чаты не видны;
  * перед платным шагом проверяет баланс кредитов, после — списывает фактическую стоимость
    (Grok — по токенам из ответа xAI, WaveSpeed — по цене генерации) через /charge.

Секрет PS_INTERNAL_TOKEN общий с model-mate (AGENT_INTERNAL_TOKEN) — без него внутренние вызовы отклоняются.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request

API = (os.environ.get("PS_HOSTED_API") or "").rstrip("/")
TOKEN = os.environ.get("PS_INTERNAL_TOKEN") or ""
ENABLED = bool(API)
SESSION_TTL = 30.0

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


class AuthError(Exception):
    def __init__(self, code: int, message: str, reason: str | None = None):
        super().__init__(message)
        self.code, self.reason = code, reason


class NoCredits(RuntimeError):
    pass


def _call(path: str, payload: dict | None = None, headers: dict | None = None, timeout: float = 20.0) -> dict:
    h = {"Content-Type": "application/json", "X-Internal-Token": TOKEN, "User-Agent": "persona-studio-hosted/1.0"}
    h.update(headers or {})
    req = urllib.request.Request(API + path, data=json.dumps(payload or {}).encode(), method="POST", headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8", "replace")).get("detail")
        except Exception:
            detail = None
        if isinstance(detail, dict):
            raise AuthError(e.code, detail.get("message") or str(detail), detail.get("reason"))
        raise AuthError(e.code, str(detail or f"HTTP {e.code}"))


def session(headers) -> dict:
    """Кто пришёл (по cookie/Bearer пользователя model-mate) + ключи и тариф. Кэш 30 с."""
    auth = headers.get("Authorization") or ""
    cookie = headers.get("Cookie") or ""
    if not auth and not cookie:
        raise AuthError(401, "Нужно войти в аккаунт")
    k = hashlib.sha256((auth + "|" + cookie).encode()).hexdigest()
    now = time.time()
    with _lock:
        hit = _cache.get(k)
        if hit and now - hit[0] < SESSION_TTL:
            return hit[1]
    fwd = {}
    if auth:
        fwd["Authorization"] = auth
    if cookie:
        fwd["Cookie"] = cookie
    ctx = _call("/session", {}, fwd)
    with _lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[k] = (now, ctx)
    return ctx


def forget_balance(ctx: dict) -> None:
    """После списания — сбросить кэш сессий владельца, чтобы баланс в интерфейсе обновился."""
    with _lock:
        for k in [k for k, (_, c) in _cache.items() if c.get("owner_id") == ctx.get("owner_id")]:
            _cache.pop(k, None)


def credits(ctx: dict, usd: float) -> int:
    """Сколько кредитов спишется за usd себестоимости (для подсказок в интерфейсе)."""
    if usd <= 0:
        return 0
    return max(1, math.ceil(usd * float(ctx.get("multiplier") or 2.0) * 100 - 1e-9))


def check(ctx: dict, usd: float) -> str | None:
    """None — денег хватает; иначе текст для пользователя."""
    r = _call("/check", {"owner_id": ctx["owner_id"], "usd": round(float(usd), 5)})
    if r.get("ok"):
        return None
    return (f"недостаточно кредитов: нужно ≈ {r.get('need')} кр., на балансе {r.get('balance')} кр. "
            "Пополните баланс в разделе «Тариф и баланс»")


def charge(ctx: dict, kind: str, *, usd: float = 0.0, usage: dict | None = None, model: str | None = None,
           meta: dict | None = None) -> dict:
    """Списать фактическую стоимость. Ошибку сети не пробрасываем (результат уже у пользователя), но логируем."""
    body = {"owner_id": ctx["owner_id"], "actor_id": ctx.get("actor_id"), "kind": kind, "usd": round(float(usd), 6),
            "usage": usage or None, "model": model, "meta": meta or {}}
    last = None
    for _ in range(2):
        try:
            r = _call("/charge", body)
            forget_balance(ctx)
            return r
        except (AuthError, OSError) as e:
            last = e
            time.sleep(1)
    print(f"[hosted] не удалось списать {kind} {usd} owner={ctx.get('owner_id')}: {last}")
    return {"credits": 0, "error": str(last)}
