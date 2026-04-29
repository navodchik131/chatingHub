from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


def _wavespeed_base() -> str:
    return (settings.wavespeed_api_base or "https://api.wavespeed.ai").rstrip("/")


def _seedream_edit_post_path() -> str:
    p = (settings.wavespeed_seedream_edit_path or "").strip() or "/api/v3/alibaba/wan-2.7/image-edit-pro"
    return p if p.startswith("/") else f"/{p}"


def _is_wan_27_image_edit_path(post_path: str) -> bool:
    s = (post_path or "").lower()
    return "wan" in s and "image-edit" in s


def _format_size_for_wavespeed_path(post_path: str, size: str) -> str:
    """WAN 2.7: `width*height`; Seedream — `widthxheight` (см. доки)."""
    s = size.strip()
    if _is_wan_27_image_edit_path(post_path) and "x" in s.lower() and "*" not in s:
        return s.replace("x", "*").replace("X", "*")
    return s


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


def _is_wavespeed_task_json_url(u: str) -> bool:
    """
    URL опроса задачи (JSON), не CDN-картинка — в <img> даёт net::ERR_BLOCKED_BY_ORB.
    Не путать с data.urls.get в ответе WaveSpeed.
    """
    s = (u or "").strip().lower()
    if "wavespeed" in s and "/api/v3/predictions/" in s:
        return True
    if "/predictions/" in s and s.rstrip("/").endswith("/result"):
        return True
    return False


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
    """
    WaveSpeed: data.outputs — массив URL; в ряде ответов встречаются одна строка-URL
    или JSON-строка с массивом (нестыковки в OpenAPI).
    """
    if outputs is None:
        return None
    if isinstance(outputs, str):
        s = outputs.strip()
        if s.startswith("http://") or s.startswith("https://"):
            if _is_wavespeed_task_json_url(s):
                return None
            return s
        if s.startswith("["):
            try:
                return _first_output_url(json.loads(s))
            except (json.JSONDecodeError, TypeError):
                return None
        return None
    if isinstance(outputs, dict):
        for k in ("url", "uri", "image", "output", "src", "result"):
            v = outputs.get(k)
            if isinstance(v, str) and v.strip().startswith("http"):
                s = v.strip()
                if not _is_wavespeed_task_json_url(s):
                    return s
        return None
    if not isinstance(outputs, list) or not outputs:
        return None
    first = outputs[0]
    if isinstance(first, str) and first.strip():
        s = first.strip()
        if _is_wavespeed_task_json_url(s):
            return None
        return s
    if isinstance(first, dict):
        for k in ("url", "uri", "image", "output", "src"):
            v = first.get(k)
            if isinstance(v, str) and v.strip():
                v = v.strip()
                if v.startswith("http") and not _is_wavespeed_task_json_url(v):
                    return v
    return None


def _image_url_from_prediction(d: dict[str, Any]) -> str | None:
    """
    URL готового изображения (CDN). Не data.urls.get — это JSON /predictions/.../result (ORB в <img>).
    """
    for key in ("outputs", "output", "image_url"):
        if key in d:
            u = _first_output_url(d.get(key))
            if u and not _is_wavespeed_task_json_url(u):
                return u
            v = d.get(key)
            if isinstance(v, str) and v.strip().startswith("http"):
                s = v.strip()
                if not _is_wavespeed_task_json_url(s):
                    return s
    for key in ("result", "url"):
        if key not in d:
            continue
        v = d.get(key)
        if isinstance(v, str) and v.strip().startswith("http"):
            s = v.strip()
            if not _is_wavespeed_task_json_url(s):
                return s
    imgs = d.get("images")
    if isinstance(imgs, list) and imgs:
        u = _first_output_url(imgs)
        if u and not _is_wavespeed_task_json_url(u):
            return u
    return None


def _task_id_from_prediction(d: dict[str, Any]) -> str | None:
    for k in ("id", "taskId", "task_id", "prediction_id", "requestId"):
        v = d.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
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


async def _wavespeed_post_json_and_resolve_image_url(
    *,
    api_key: str,
    full_post_url: str,
    body: dict[str, Any],
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 90,
) -> str:
    """Общий POST + разбор ответа / опрос prediction до появления URL картинки."""
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    base = _wavespeed_base()
    async with httpx.AsyncClient(timeout=timeout_submit) as client:
        r = None
        for attempt in range(3):
            r = await client.post(full_post_url, headers=headers, json=body)
            if r.status_code < 500:
                break
            log.warning(
                "wavespeed submit %s (attempt %s), retry: %s",
                r.status_code,
                attempt + 1,
                (r.text or "")[:500],
            )
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
        u0 = _image_url_from_prediction(d)
        if u0:
            return u0

        task_id = _task_id_from_prediction(d)
        status = (d.get("status") or "").lower()
        if status == "failed":
            raise RuntimeError(str(d.get("error") or "WaveSpeed task failed"))
        if status == "completed":
            raise RuntimeError(
                str(
                    d.get("error")
                    or "WaveSpeed: статус completed, но нет ссылки на изображение (проверьте ответ в логах сервера)"
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
            if st == "failed":
                raise RuntimeError(str(pd.get("error") or "WaveSpeed task failed"))
            if st == "completed":
                u = _image_url_from_prediction(pd)
                if u:
                    return u
                raise RuntimeError(
                    str(
                        pd.get("error")
                        or "WaveSpeed: задача completed, но нет URL изображения (неизвестный формат outputs)"
                    )
                )
            u = _image_url_from_prediction(pd)
            if u:
                return u

    raise RuntimeError("WaveSpeed: timeout waiting for result")


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
    Image edit через WaveSpeed: путь `WAVESPEED_SEEDREAM_EDIT_PATH` (WAN 2.7 / Seedream v5 / v4.5 / …).
    """
    if not image_urls:
        raise RuntimeError("no image URLs")
    if not (prompt or "").strip():
        raise RuntimeError("empty prompt")

    base = _wavespeed_base()
    post_path = _seedream_edit_post_path()
    url = f"{base}{post_path}"
    is_wan = _is_wan_27_image_edit_path(post_path)
    if is_wan:
        # https://wavespeed.ai/docs/docs-api/alibaba/alibaba-wan-2.7-image-edit
        n_img = 9
        body = {
            "images": image_urls[:n_img],
            "prompt": prompt.strip(),
            "seed": int(settings.wavespeed_wan_image_edit_seed),
        }
        if size and size.strip():
            body["size"] = _format_size_for_wavespeed_path(post_path, size)
    else:
        body = {
            "images": image_urls[:10],
            "prompt": prompt.strip(),
            "enable_sync_mode": bool(settings.wavespeed_seedream_sync),
            "enable_base64_output": False,
        }
        if size and size.strip():
            body["size"] = _format_size_for_wavespeed_path(post_path, size)
        fmt = (settings.wavespeed_seedream_output_format or "").strip().lower()
        if fmt in ("jpeg", "jpg", "png"):
            body["output_format"] = "jpeg" if fmt in ("jpeg", "jpg") else "png"

    _apply_wavespeed_extra_body(body)
    log.debug(
        "wavespeed submit wan=%s path=%s images=%s prompt_len=%s keys=%s",
        is_wan,
        post_path,
        len(body.get("images") or []),
        len(str(body.get("prompt") or "")),
        list(body.keys()),
    )

    return await _wavespeed_post_json_and_resolve_image_url(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )


def _wavespeed_upscaler_post_path() -> str:
    p = (settings.wavespeed_image_upscaler_path or "").strip() or "/api/v3/wavespeed-ai/image-upscaler"
    return p if p.startswith("/") else f"/{p}"


async def wavespeed_image_upscale_url(
    *,
    api_key: str,
    image_url: str,
    target_resolution: str = "4k",
    output_format: str = "png",
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 90,
) -> str:
    """Image Upscaler WaveSpeed: публичный HTTPS URL входного изображения."""
    u = (image_url or "").strip()
    if not u:
        raise RuntimeError("empty image URL")
    tres = (target_resolution or "4k").strip().lower()
    if tres not in ("2k", "4k", "8k"):
        raise RuntimeError("target_resolution must be 2k, 4k or 8k")
    fmt = (output_format or "png").strip().lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in ("jpeg", "png", "webp"):
        fmt = "png"
    body: dict[str, Any] = {
        "image": u,
        "target_resolution": tres,
        "output_format": fmt,
        "enable_base64_output": False,
        "enable_sync_mode": bool(settings.wavespeed_upscale_sync),
    }
    path = _wavespeed_upscaler_post_path()
    full_url = f"{_wavespeed_base()}{path}"
    log.debug("wavespeed upscale post=%s target=%s fmt=%s", path, tres, fmt)
    return await _wavespeed_post_json_and_resolve_image_url(
        api_key=api_key,
        full_post_url=full_url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )
