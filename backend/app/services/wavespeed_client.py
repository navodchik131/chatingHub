from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

SEEDREAM_V45_EDIT_PATH = "/api/v3/bytedance/seedream-v4.5/edit"


def _wavespeed_base() -> str:
    return (settings.wavespeed_api_base or "https://api.wavespeed.ai").rstrip("/")


def _apply_wavespeed_extra_body(body: dict[str, Any]) -> None:
    raw = (settings.wavespeed_extra_json or "").strip()
    if not raw:
        return
    try:
        extra = json.loads(raw)
        if isinstance(extra, dict):
            body.update(extra)
    except json.JSONDecodeError:
        log.warning("WAVESPEED_EXTRA_JSON: невалидный JSON, пропускаем")


def _wavespeed_envelope_error(resp_json: dict[str, Any]) -> str | None:
    """
    WaveSpeed отдаёт обёртку {code, message, data}. HTTP может быть 200, а code в JSON — ошибка.
    """
    code = resp_json.get("code")
    if code is None:
        return None
    try:
        c = int(code)
    except (TypeError, ValueError):
        return None
    if c == 200:
        return None
    parts: list[str] = []
    m = str(resp_json.get("message") or "").strip()
    if m:
        parts.append(m)
    data = resp_json.get("data")
    if isinstance(data, dict):
        e = str(data.get("error") or "").strip()
        if e:
            parts.append(e)
    return " — ".join(parts) if parts else f"WaveSpeed вернул code={c}"


def _first_output_url(outputs: Any) -> str | None:
    """WaveSpeed обычно отдаёт outputs: [url, ...], иногда элементы-объекты с полем url."""
    if not isinstance(outputs, list) or not outputs:
        return None
    first = outputs[0]
    if isinstance(first, str) and first.strip():
        return first.strip()
    if isinstance(first, dict):
        for k in ("url", "uri", "image", "output", "src"):
            v = first.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _unwrap_data(resp_json: dict[str, Any]) -> dict[str, Any]:
    """Достаёт объект prediction из ответа; при пустом data — понятная ошибка."""
    data = resp_json.get("data")
    if isinstance(data, dict):
        return data
    if data is None:
        hint = str(resp_json.get("message") or "").strip()
        raise RuntimeError(
            hint
            or "WaveSpeed: пустой data в ответе (проверьте API-ключ, баланс и публичный HTTPS URL референсов)"
        )
    raise RuntimeError(
        str(resp_json.get("message") or "WaveSpeed: некорректное поле data в ответе")
    )


async def seedream_v45_edit_image_url(
    *,
    api_key: str,
    image_urls: list[str],
    prompt: str,
    size: str | None = None,
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 90,
) -> str:
    """
    Отправка задачи Seedream v4.5 Edit (sync при возможности, иначе polling).
    Возвращает URL первого выходного изображения.
    """
    if not image_urls:
        raise RuntimeError("no image URLs")
    if not (prompt or "").strip():
        raise RuntimeError("empty prompt")

    base = _wavespeed_base()
    url = f"{base}{SEEDREAM_V45_EDIT_PATH}"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "images": image_urls[:10],
        "prompt": prompt.strip(),
        # Документация WaveSpeed по умолчанию false; sync=true иногда даёт пустой/ошибочный ответ при HTTP 200.
        "enable_sync_mode": False,
        "enable_base64_output": False,
    }
    if size and size.strip():
        body["size"] = size.strip()

    _apply_wavespeed_extra_body(body)
    log.debug(
        "wavespeed submit: images=%s prompt_len=%s keys=%s",
        len(body.get("images") or []),
        len(str(body.get("prompt") or "")),
        list(body.keys()),
    )

    async with httpx.AsyncClient(timeout=timeout_submit) as client:
        r = None
        for attempt in range(3):
            r = await client.post(url, headers=headers, json=body)
            if r.status_code < 500:
                break
            last_err = (r.text or "")[:500]
            log.warning("wavespeed submit %s (attempt %s), retry: %s", r.status_code, attempt + 1, last_err)
            await asyncio.sleep(2.0 * (attempt + 1))
        if r is None:
            raise RuntimeError("WaveSpeed: пустой ответ")
        if r.status_code >= 400:
            detail = (r.text or "")[:2000]
            try:
                ej = r.json()
                if isinstance(ej, dict):
                    detail = str(
                        ej.get("message")
                        or (ej.get("data") or {}).get("error")
                        or ej.get("error")
                        or detail
                    )
            except Exception:
                pass
            log.warning("wavespeed submit %s: %s", r.status_code, (r.text or "")[:1200])
            raise RuntimeError(
                f"WaveSpeed: {detail or f'HTTP {r.status_code}'}. "
                "Проверьте баланс, https://status.wavespeed.ai и публичный HTTPS URL картинок (PUBLIC_APP_URL)."
            )

        try:
            resp = r.json()
        except Exception as e:
            log.warning("wavespeed submit: не JSON %s", (r.text or "")[:800])
            raise RuntimeError("WaveSpeed: невалидный JSON в ответе") from e
        if not isinstance(resp, dict):
            raise RuntimeError("WaveSpeed: неожиданный формат ответа")
        env_err = _wavespeed_envelope_error(resp)
        if env_err:
            log.warning("wavespeed submit envelope: %s", env_err)
            raise RuntimeError(
                f"WaveSpeed: {env_err}. Проверьте баланс и параметры; если ошибка общая (try again) — подождите и повторите."
            )
        d = _unwrap_data(resp)
        outs = d.get("outputs")
        u0 = _first_output_url(outs)
        if u0:
            return u0

        task_id = d.get("id")
        status = (d.get("status") or "").lower()
        if status == "failed":
            raise RuntimeError(str(d.get("error") or "WaveSpeed task failed"))
        if status == "completed":
            raise RuntimeError(
                str(
                    d.get("error")
                    or "WaveSpeed: статус completed, но нет ссылки на изображение в outputs"
                )
            )

        if not task_id:
            raise RuntimeError(
                str(d.get("error") or "WaveSpeed: нет task id и outputs (проверьте ответ API)")
            )

        result_url = f"{base}/api/v3/predictions/{task_id}/result"
        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)
            pr = await client.get(result_url, headers={"Authorization": headers["Authorization"]})
            if pr.status_code >= 400:
                log.warning("wavespeed poll %s: %s", pr.status_code, (pr.text or "")[:800])
                continue
            try:
                raw_poll = pr.json()
            except Exception:
                log.warning("wavespeed poll: не JSON %s", (pr.text or "")[:400])
                continue
            if not isinstance(raw_poll, dict):
                continue
            penv = _wavespeed_envelope_error(raw_poll)
            if penv:
                log.warning("wavespeed poll envelope: %s", penv)
                raise RuntimeError(
                    f"WaveSpeed: {penv}. Проверьте баланс и ссылку на результат задачи; при 5xx повторите позже."
                )
            pd = _unwrap_data(raw_poll)
            st = (pd.get("status") or "").lower()
            outs2 = pd.get("outputs")
            if st == "failed":
                raise RuntimeError(str(pd.get("error") or "WaveSpeed task failed"))
            if st == "completed":
                u = _first_output_url(outs2)
                if u:
                    return u
                raise RuntimeError(
                    str(
                        pd.get("error")
                        or "WaveSpeed: задача completed, но outputs пустой или неизвестный формат"
                    )
                )
            u = _first_output_url(outs2)
            if u:
                return u

    raise RuntimeError("WaveSpeed: timeout waiting for result")
