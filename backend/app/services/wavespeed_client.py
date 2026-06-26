from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


def _wavespeed_base() -> str:
    return (settings.wavespeed_api_base or "https://api.wavespeed.ai").rstrip("/")


def _seedream_edit_post_path() -> str:
    p = (settings.wavespeed_seedream_edit_path or "").strip() or "/api/v3/alibaba/wan-2.7/image-edit"
    return p if p.startswith("/") else f"/{p}"


# Фиксированные пути WAN 2.7 (переключение в UI при WAVESPEED_SEEDREAM_EDIT_PATH = WAN).
WAN_27_IMAGE_EDIT_STANDARD_PATH = "/api/v3/alibaba/wan-2.7/image-edit"
WAN_27_IMAGE_EDIT_PRO_PATH = "/api/v3/alibaba/wan-2.7/image-edit-pro"
SEEDREAM_V45_EDIT_PATH = "/api/v3/bytedance/seedream-v4.5/edit"
GPT_IMAGE_2_EDIT_PATH = "/api/v3/openai/gpt-image-2/edit"
WAVESPEED_MEDIA_UPLOAD_PATH = "/api/v3/media/upload/binary"


def resolve_studio_image_edit_post_path(*, wan_edit_tier: str | None) -> str:
    """
    Если в настройках указан WAN 2.7 image-edit — подменяем путь по запросу UI (standard | pro).
    Для Seedream и любых не-WAN путей возвращаем путь из .env без изменений.
    """
    cfg = (settings.wavespeed_seedream_edit_path or "").strip() or WAN_27_IMAGE_EDIT_STANDARD_PATH
    configured = cfg if cfg.startswith("/") else f"/{cfg}"
    if not _is_wan_27_image_edit_path(configured):
        return configured
    t = (wan_edit_tier or "standard").strip().lower()
    if t == "pro":
        return WAN_27_IMAGE_EDIT_PRO_PATH
    return WAN_27_IMAGE_EDIT_STANDARD_PATH


def studio_wan_edit_tier_switch_available() -> bool:
    """True — в студии можно переключать обычный WAN / Pro (endpoint в .env относится к WAN 2.7)."""
    return _is_wan_27_image_edit_path(_seedream_edit_post_path())


def _is_wan_27_image_edit_path(post_path: str) -> bool:
    s = (post_path or "").lower()
    return "wan" in s and "image-edit" in s


def _format_size_for_wavespeed_path(post_path: str, size: str) -> str:
    """WAN 2.7: `width*height`; Seedream — `widthxheight` (см. доки)."""
    s = size.strip()
    if _is_wan_27_image_edit_path(post_path) and "x" in s.lower() and "*" not in s:
        return s.replace("x", "*").replace("X", "*")
    return s


def _format_size_z_image_inpaint(size: str) -> str:
    """Z-Image Inpaint: в доке размер — `width*height`."""
    s = size.strip()
    if "x" in s.lower() and "*" not in s:
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


def _wavespeed_task_failed_error(resp_json: dict[str, Any]) -> str | None:
    """
    Ошибка конкретной задачи (data.status=failed, data.error) — приоритетнее message обёртки.
    В UI WaveSpeed часто видна именно data.error (модерация), а в API ещё code/message про баланс.
    """
    data = resp_json.get("data")
    if not isinstance(data, dict):
        return None
    if (data.get("status") or "").lower() != "failed":
        return None
    err = str(data.get("error") or "").strip()
    return err or "WaveSpeed task failed"


def format_wavespeed_user_error(message: str) -> str:
    """Текст ошибки WaveSpeed для UI (без лишних подсказок про PUBLIC_APP_URL)."""
    raw = (message or "").strip()
    body = raw.split(":", 1)[1].strip() if raw.lower().startswith("wavespeed:") else raw
    if not body:
        return "WaveSpeed: ошибка запроса к провайдеру."
    low = body.lower()
    if (
        "<html" in low
        or "gateway time" in low
        or "gateway timeout" in low
        or ("504" in body and "http" in low)
    ):
        return (
            "WaveSpeed: сервер провайдера временно недоступен (504). "
            "Подождите 1–2 минуты и обновите страницу — картинка могла уже сохраниться в архиве."
        )
    if "insufficient credits" in low or "top up" in low:
        return (
            f"WaveSpeed: {body} "
            "Пополните баланс на wavespeed.ai (API-ключ в «Подключения»)."
        )
    if (
        "flagged" in low
        or "potentially sensitive" in low
        or ("sensitive" in low and "content" in low)
    ):
        return (
            f"WaveSpeed: {body} "
            "Контент отклонён модерацией — попробуйте другой промпт или референсы."
        )
    if "provider rejected" in low or "check your inputs" in low:
        return (
            f"WaveSpeed: {body} "
            "Проверьте формат и содержание загруженных изображений."
        )
    return f"WaveSpeed: {body}"


def wavespeed_is_sensitive_content_error(message: str | None) -> bool:
    low = (message or "").lower()
    return (
        "flagged" in low
        or "potentially sensitive" in low
        or ("sensitive" in low and "content" in low)
    )


def wavespeed_is_video_poll_timeout_error(message: str | None) -> bool:
    """Локальный таймаут опроса — задача на WaveSpeed может ещё быть в processing."""
    return "timeout waiting for video" in (message or "").lower()


def _wavespeed_raise_from_response(resp_json: dict[str, Any], *, context: str) -> None:
    task_err = _wavespeed_task_failed_error(resp_json)
    if task_err:
        log.warning("wavespeed %s task failed: %s", context, task_err[:500])
        raise RuntimeError(format_wavespeed_user_error(task_err))
    env_err = _wavespeed_envelope_error(resp_json)
    if env_err:
        log.warning("wavespeed %s envelope: %s", context, env_err[:500])
        raise RuntimeError(format_wavespeed_user_error(env_err))


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
            or "WaveSpeed: пустой data в ответе (проверьте API-ключ и баланс на wavespeed.ai)"
        )
    raise RuntimeError(
        str(resp_json.get("message") or "WaveSpeed: некорректное поле data в ответе")
    )


@dataclass(frozen=True, slots=True)
class WaveSpeedImageResult:
    url: str
    task_id: str | None = None


@dataclass(frozen=True, slots=True)
class WaveSpeedSubmitOutcome:
    """Ответ submit: сразу URL и/или task_id для опроса."""

    immediate_url: str | None = None
    task_id: str | None = None


def _is_transient_wavespeed_http(status_code: int) -> bool:
    return status_code in (502, 503, 504)


async def wavespeed_poll_image_by_task_id(
    *,
    api_key: str,
    task_id: str,
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 120,
    max_transient_poll_errors: int = 90,
) -> WaveSpeedImageResult:
    """Опрашивает /predictions/{id}/result до completed или ошибки."""
    tid = (task_id or "").strip()
    if not tid:
        raise RuntimeError("WaveSpeed: пустой task id")
    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    base = _wavespeed_base()
    result_url = f"{base}/api/v3/predictions/{tid}/result"
    transient_errors = 0
    async with httpx.AsyncClient(timeout=timeout_submit) as client:
        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)
            pr = await client.get(result_url, headers=headers)
            if pr.status_code >= 400:
                if _is_transient_wavespeed_http(pr.status_code):
                    transient_errors += 1
                    if transient_errors > max_transient_poll_errors:
                        raise RuntimeError(
                            format_wavespeed_user_error(
                                f"HTTP {pr.status_code} Gateway timeout при опросе результата"
                            )
                        )
                    wait_s = min(30.0, 2.0 * transient_errors)
                    log.warning(
                        "wavespeed poll transient %s, wait %.0fs: %s",
                        pr.status_code,
                        wait_s,
                        (pr.text or "")[:200],
                    )
                    await asyncio.sleep(wait_s)
                    continue
                try:
                    ej = pr.json()
                    if isinstance(ej, dict):
                        _wavespeed_raise_from_response(ej, context="poll-http")
                except RuntimeError:
                    raise
                except Exception:
                    pass
                log.warning("wavespeed poll %s: %s", pr.status_code, (pr.text or "")[:800])
                continue
            try:
                raw_poll = pr.json()
            except Exception:
                log.warning("wavespeed poll: не JSON %s", (pr.text or "")[:400])
                continue
            if not isinstance(raw_poll, dict):
                continue
            _wavespeed_raise_from_response(raw_poll, context="poll")
            pd = _unwrap_data(raw_poll)
            st = (pd.get("status") or "").lower()
            if st == "failed":
                raise RuntimeError(
                    format_wavespeed_user_error(str(pd.get("error") or "task failed"))
                )
            if st == "completed":
                u = _image_url_from_prediction(pd)
                if u:
                    return WaveSpeedImageResult(url=u, task_id=tid)
                raise RuntimeError(
                    format_wavespeed_user_error(
                        str(
                            pd.get("error")
                            or "задача completed, но нет URL изображения"
                        )
                    )
                )
            u = _image_url_from_prediction(pd)
            if u:
                return WaveSpeedImageResult(url=u, task_id=tid)

    raise RuntimeError("WaveSpeed: timeout waiting for result")


async def _wavespeed_submit_image_prediction(
    *,
    api_key: str,
    full_post_url: str,
    body: dict[str, Any],
    timeout_submit: float = 300.0,
) -> WaveSpeedSubmitOutcome:
    """
    Submit prediction. Не повторяем POST при 502/503/504: шлюз мог оборвать ответ,
    а задача на стороне WaveSpeed уже создана — повторный POST = дубликат и списание.
    """
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout_submit) as client:
        r: httpx.Response | None = None
        for attempt in range(3):
            try:
                r = await client.post(full_post_url, headers=headers, json=body)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
                if attempt >= 2:
                    raise RuntimeError(
                        format_wavespeed_user_error(
                            "таймаут или сеть при отправке задачи в WaveSpeed"
                        )
                    ) from e
                log.warning(
                    "wavespeed submit network error (attempt %s), retry: %s",
                    attempt + 1,
                    e,
                )
                await asyncio.sleep(2.0 * (attempt + 1))
                continue
            if r.status_code < 500:
                break
            if _is_transient_wavespeed_http(r.status_code):
                log.warning(
                    "wavespeed submit %s: no POST retry (avoid duplicate tasks): %s",
                    r.status_code,
                    (r.text or "")[:500],
                )
                break
            if attempt >= 2:
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
            try:
                ej = r.json()
                if isinstance(ej, dict):
                    _wavespeed_raise_from_response(ej, context="submit-http")
            except RuntimeError:
                raise
            except Exception:
                pass
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
                format_wavespeed_user_error(detail or f"HTTP {r.status_code}")
            )

        try:
            resp = r.json()
        except Exception as e:
            log.warning("wavespeed submit: не JSON %s", (r.text or "")[:800])
            raise RuntimeError("WaveSpeed: невалидный JSON в ответе") from e
        if not isinstance(resp, dict):
            raise RuntimeError("WaveSpeed: неожиданный формат ответа")
        _wavespeed_raise_from_response(resp, context="submit")
        d = _unwrap_data(resp)
        u0 = _image_url_from_prediction(d)
        task_id = _task_id_from_prediction(d)
        if u0:
            return WaveSpeedSubmitOutcome(immediate_url=u0, task_id=task_id)
        status = (d.get("status") or "").lower()
        if status == "failed":
            raise RuntimeError(
                format_wavespeed_user_error(str(d.get("error") or "task failed"))
            )
        if status == "completed":
            raise RuntimeError(
                format_wavespeed_user_error(
                    str(
                        d.get("error")
                        or "статус completed, но нет ссылки на изображение"
                    )
                )
            )
        if not task_id:
            raise RuntimeError(
                format_wavespeed_user_error(
                    str(d.get("error") or "нет task id и outputs")
                )
            )
        return WaveSpeedSubmitOutcome(immediate_url=None, task_id=task_id)


async def _wavespeed_post_json_and_resolve_image_url(
    *,
    api_key: str,
    full_post_url: str,
    body: dict[str, Any],
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 120,
) -> WaveSpeedImageResult:
    """Общий POST + разбор ответа / опрос prediction до появления URL картинки."""
    submitted = await _wavespeed_submit_image_prediction(
        api_key=api_key,
        full_post_url=full_post_url,
        body=body,
        timeout_submit=timeout_submit,
    )
    if submitted.immediate_url:
        return WaveSpeedImageResult(url=submitted.immediate_url, task_id=submitted.task_id)
    return await wavespeed_poll_image_by_task_id(
        api_key=api_key,
        task_id=submitted.task_id or "",
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )


async def seedream_v45_edit_image_url(
    *,
    api_key: str,
    image_urls: list[str],
    prompt: str,
    size: str | None = None,
    wan_edit_tier: str | None = None,
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 120,
) -> WaveSpeedImageResult:
    """
    Image edit через WaveSpeed: путь из `resolve_studio_image_edit_post_path`
    (WAN 2.7 standard/pro по UI или Seedream / кастом из .env).
    """
    if not image_urls:
        raise RuntimeError("no image URLs")
    if not (prompt or "").strip():
        raise RuntimeError("empty prompt")

    base = _wavespeed_base()
    post_path = resolve_studio_image_edit_post_path(wan_edit_tier=wan_edit_tier)
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


async def wavespeed_upload_image_bytes(
    *,
    api_key: str,
    data: bytes,
    filename: str = "image.jpg",
    content_type: str = "image/jpeg",
    timeout: float = 120.0,
) -> str:
    """Загрузка в WaveSpeed Media; URL для полей images/image в моделях."""
    if not data:
        raise RuntimeError("empty image bytes")
    base = _wavespeed_base()
    url = f"{base}{WAVESPEED_MEDIA_UPLOAD_PATH}"
    headers = {"Authorization": f"Bearer {api_key}"}
    ct = (content_type or "image/jpeg").strip() or "image/jpeg"
    fname = (filename or "image.jpg").strip() or "image.jpg"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            url,
            headers=headers,
            files={"file": (fname, data, ct)},
        )
    if r.status_code >= 400:
        detail = (r.text or "")[:1500]
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
        raise RuntimeError(f"WaveSpeed upload: {detail or f'HTTP {r.status_code}'}")
    try:
        resp = r.json()
    except Exception as e:
        raise RuntimeError("WaveSpeed upload: невалидный JSON") from e
    if not isinstance(resp, dict):
        raise RuntimeError("WaveSpeed upload: неожиданный ответ")
    env_err = _wavespeed_envelope_error(resp)
    if env_err:
        raise RuntimeError(f"WaveSpeed upload: {env_err}")
    data_obj = resp.get("data")
    if isinstance(data_obj, dict):
        for key in ("download_url", "url"):
            u = data_obj.get(key)
            if isinstance(u, str) and u.strip().startswith("http"):
                return u.strip()
    raise RuntimeError("WaveSpeed upload: нет download_url в ответе")


async def seedream_v45_bootstrap_edit_image_url(
    *,
    api_key: str,
    image_urls: list[str],
    prompt: str,
    size: str | None = None,
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 120,
) -> WaveSpeedImageResult:
    """Создание базового кадра модели — всегда Seedream v4.5 edit (не WAN из .env)."""
    if not image_urls:
        raise RuntimeError("no image URLs")
    if not (prompt or "").strip():
        raise RuntimeError("empty prompt")
    post_path = SEEDREAM_V45_EDIT_PATH
    body: dict[str, Any] = {
        "images": image_urls[:10],
        "prompt": prompt.strip(),
        "enable_sync_mode": bool(settings.wavespeed_seedream_sync),
        "enable_base64_output": False,
    }
    if size and size.strip():
        s = size.strip()
        if "x" in s.lower() and "*" not in s:
            s = s.replace("x", "*").replace("X", "*")
        body["size"] = s
    _apply_wavespeed_extra_body(body)
    url = f"{_wavespeed_base()}{post_path}"
    return await _wavespeed_post_json_and_resolve_image_url(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )


async def gpt_image_2_edit_image_url(
    *,
    api_key: str,
    image_urls: list[str],
    prompt: str,
    aspect_ratio: str = "16:9",
    resolution: str = "1k",
    quality: str = "medium",
    output_format: str = "png",
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 120,
    on_task_submitted: Callable[[str], Awaitable[None]] | None = None,
) -> WaveSpeedImageResult:
    """Развёртка модели — OpenAI GPT Image 2 Edit на WaveSpeed."""
    if not image_urls:
        raise RuntimeError("no image URLs")
    if not (prompt or "").strip():
        raise RuntimeError("empty prompt")
    ar = (aspect_ratio or "16:9").strip()
    res = (resolution or "1k").strip().lower()
    qual = (quality or "medium").strip().lower()
    fmt = (output_format or "png").strip().lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in ("jpeg", "png", "webp"):
        fmt = "png"
    post_path = GPT_IMAGE_2_EDIT_PATH
    body: dict[str, Any] = {
        "images": image_urls[:10],
        "prompt": prompt.strip(),
        "aspect_ratio": ar,
        "resolution": res,
        "quality": qual,
        "output_format": fmt,
        # Всегда async: sync держит POST минутами → 504 stgw и наш retry плодил дубликаты.
        "enable_sync_mode": False,
        "enable_base64_output": False,
    }
    _apply_wavespeed_extra_body(body)
    url = f"{_wavespeed_base()}{post_path}"
    submitted = await _wavespeed_submit_image_prediction(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=min(timeout_submit, 120.0),
    )
    if on_task_submitted and submitted.task_id:
        await on_task_submitted(submitted.task_id)
    if submitted.immediate_url:
        return WaveSpeedImageResult(
            url=submitted.immediate_url, task_id=submitted.task_id
        )
    return await wavespeed_poll_image_by_task_id(
        api_key=api_key,
        task_id=submitted.task_id or "",
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
    max_polls: int = 120,
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
    res = await _wavespeed_post_json_and_resolve_image_url(
        api_key=api_key,
        full_post_url=full_url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )
    return res.url


def _z_image_inpaint_post_path() -> str:
    p = (settings.wavespeed_z_image_inpaint_path or "").strip() or "/api/v3/wavespeed-ai/z-image/turbo-inpaint"
    return p if p.startswith("/") else f"/{p}"


async def z_image_turbo_inpaint_image_url(
    *,
    api_key: str,
    image_url: str,
    mask_image_url: str,
    prompt: str,
    size: str | None = None,
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 120,
) -> WaveSpeedImageResult:
    """
    Z-Image Turbo Inpaint: публичные HTTPS URL изображения и маски (одинаковый размер).
    Док: wavespeed.ai — z-image/turbo-inpaint.
    """
    iu = (image_url or "").strip()
    mu = (mask_image_url or "").strip()
    if not iu or not mu:
        raise RuntimeError("empty image or mask URL")
    if not (prompt or "").strip():
        raise RuntimeError("empty prompt")

    path = _z_image_inpaint_post_path()
    full_url = f"{_wavespeed_base()}{path}"
    body: dict[str, Any] = {
        "image": iu,
        "mask_image": mu,
        "prompt": prompt.strip(),
    }
    if (
        not settings.wavespeed_z_image_inpaint_omit_size
        and size
        and size.strip()
    ):
        body["size"] = _format_size_z_image_inpaint(size)
    _apply_wavespeed_extra_body(body)
    log.debug(
        "wavespeed z-image inpaint path=%s size_omitted=%s",
        path,
        settings.wavespeed_z_image_inpaint_omit_size,
    )
    return await _wavespeed_post_json_and_resolve_image_url(
        api_key=api_key,
        full_post_url=full_url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )


def _nano_banana_pro_edit_post_path() -> str:
    p = (settings.wavespeed_nano_banana_pro_edit_path or "").strip() or "/api/v3/google/nano-banana-pro/edit"
    return p if p.startswith("/") else f"/{p}"


async def nano_banana_pro_edit_image_url(
    *,
    api_key: str,
    image_urls: list[str],
    prompt: str,
    aspect_ratio: str,
    wave_profile: str | None = None,
    reference_scene_description: str | None = None,
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 180,
) -> WaveSpeedImageResult:
    """
    Google Nano Banana Pro Edit: images + prompt + aspect_ratio + resolution.
    Док: /docs/docs-api/google/google-nano-banana-pro-edit
    """
    from app.services.studio_prompt_bundle import (
        compact_studio_prompt_for_nano_banana,
        nano_banana_preflight_error,
    )

    pre = nano_banana_preflight_error(
        wave_profile=wave_profile,
        reference_scene_description=reference_scene_description,
        image_urls=image_urls,
    )
    if pre:
        raise RuntimeError(pre)

    if not image_urls:
        raise RuntimeError("no image URLs")
    if not (prompt or "").strip():
        raise RuntimeError("empty prompt")

    prompt_use = compact_studio_prompt_for_nano_banana(prompt)
    ar = (aspect_ratio or "").strip()
    if ar not in (
        "1:1",
        "3:2",
        "2:3",
        "3:4",
        "4:3",
        "4:5",
        "5:4",
        "9:16",
        "16:9",
        "21:9",
    ):
        raise RuntimeError(
            f"Nano Banana: недопустимый aspect_ratio «{ar}». "
            "Доступно: 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9."
        )

    res = (settings.wavespeed_nano_banana_pro_resolution or "2k").strip().lower()
    if res not in ("1k", "2k", "4k"):
        res = "2k"
    fmt = (settings.wavespeed_nano_banana_pro_output_format or "png").strip().lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in ("png", "jpeg"):
        fmt = "png"
    path = _nano_banana_pro_edit_post_path()
    url = f"{_wavespeed_base()}{path}"
    body: dict[str, Any] = {
        "images": image_urls[:14],
        "prompt": prompt_use,
        "aspect_ratio": ar,
        "resolution": res,
        "output_format": fmt,
        "enable_sync_mode": False,
        "enable_base64_output": False,
    }
    log.info(
        "wavespeed nano-banana-pro path=%s images=%s aspect=%s res=%s sync=async prompt_chars=%s",
        path,
        len(body.get("images") or []),
        ar,
        res,
        len(prompt_use),
    )
    log.debug(
        "wavespeed nano-banana-pro path=%s images=%s aspect=%s res=%s",
        path,
        len(body.get("images") or []),
        ar,
        res,
    )
    return await _wavespeed_post_json_and_resolve_image_url(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )


NANO_BANANA_2_EDIT_PATH = "/api/v3/google/nano-banana-2/edit"


async def nano_banana_2_edit_image_url(
    *,
    api_key: str,
    image_urls: list[str],
    prompt: str,
    aspect_ratio: str = "3:4",
    timeout_submit: float = 300.0,
    poll_interval: float = 2.0,
    max_polls: int = 180,
) -> WaveSpeedImageResult:
    """Google Nano Banana 2 Edit."""
    if not image_urls:
        raise RuntimeError("no image URLs")
    if not (prompt or "").strip():
        raise RuntimeError("empty prompt")
    ar = (aspect_ratio or "3:4").strip()
    path = NANO_BANANA_2_EDIT_PATH
    url = f"{_wavespeed_base()}{path}"
    body: dict[str, Any] = {
        "images": image_urls[:14],
        "prompt": prompt.strip(),
        "aspect_ratio": ar,
        "resolution": "1k",
        "output_format": "png",
        "enable_sync_mode": False,
        "enable_base64_output": False,
    }
    _apply_wavespeed_extra_body(body)
    return await _wavespeed_post_json_and_resolve_image_url(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )


async def workflow_edit_image_url(
    *,
    api_key: str,
    wave_model_id: str,
    image_urls: list[str],
    prompt: str,
    aspect_ratio: str,
    wan_edit_tier: str = "standard",
    wave_profile: str | None = None,
    reference_scene_description: str | None = None,
    size: str | None = None,
) -> WaveSpeedImageResult:
    """WaveSpeed edit по выбору модели в workflow-редакторе."""
    model = (wave_model_id or "wan-2.7").strip().lower()
    if model == "nano-banana-pro":
        return await nano_banana_pro_edit_image_url(
            api_key=api_key,
            image_urls=image_urls,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            wave_profile=wave_profile,
            reference_scene_description=reference_scene_description,
        )
    if model == "nano-banana-2":
        return await nano_banana_2_edit_image_url(
            api_key=api_key,
            image_urls=image_urls,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
        )
    if model == "gpt-image-2":
        return await gpt_image_2_edit_image_url(
            api_key=api_key,
            image_urls=image_urls,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
        )
    if model == "wan-2.7":
        return await seedream_v45_edit_image_url(
            api_key=api_key,
            image_urls=image_urls,
            prompt=prompt,
            size=size,
            wan_edit_tier=wan_edit_tier,
        )
    raise RuntimeError(
        f"Неизвестная модель workflow: {wave_model_id}. "
        "Доступны: gpt-image-2, nano-banana-2, nano-banana-pro, wan-2.7"
    )


def _looks_like_video_asset_url(u: str) -> bool:
    s = (u or "").strip().lower().split("?")[0]
    return s.endswith((".mp4", ".webm", ".mov", ".m4v"))


def _video_url_from_prediction(d: dict[str, Any]) -> str | None:
    for key in ("outputs", "output", "video_url"):
        v = d.get(key)
        if v is None:
            continue
        u = _first_output_url(v)
        if u and u.startswith("http") and not _is_wavespeed_task_json_url(u):
            if _looks_like_video_asset_url(u):
                return u
            low = u.lower()
            if ".mp4" in low or "/video" in low or ".webm" in low:
                return u
    u2 = _first_output_url(d.get("outputs"))
    if u2 and u2.startswith("http") and not _is_wavespeed_task_json_url(u2):
        low = u2.lower()
        if ".mp4" in low or ".webm" in low or "/video" in low:
            return u2
    return None


async def _wavespeed_post_json_and_resolve_video_url(
    *,
    api_key: str,
    full_post_url: str,
    body: dict[str, Any],
    timeout_submit: float = 900.0,
    poll_interval: float = 3.0,
    max_polls: int = 180,
) -> str:
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
                "wavespeed video submit %s (attempt %s), retry: %s",
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
            log.warning("wavespeed video submit %s: %s", r.status_code, (r.text or "")[:1200])
            raise RuntimeError(format_wavespeed_user_error(detail or f"HTTP {r.status_code}"))
        try:
            resp = r.json()
        except Exception as e:
            log.warning("wavespeed video submit: не JSON %s", (r.text or "")[:800])
            raise RuntimeError("WaveSpeed: невалидный JSON в ответе") from e
        if not isinstance(resp, dict):
            raise RuntimeError("WaveSpeed: неожиданный формат ответа")
        env_err = _wavespeed_envelope_error(resp)
        if env_err:
            log.warning("wavespeed video submit envelope: %s", env_err)
            raise RuntimeError(f"WaveSpeed: {env_err}")
        d = _unwrap_data(resp)
        u0 = _video_url_from_prediction(d)
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
                    or "WaveSpeed: статус completed, но нет ссылки на видео"
                )
            )
        if not task_id:
            raise RuntimeError(
                str(d.get("error") or "WaveSpeed: нет task id и outputs для видео")
            )
        result_url = f"{base}/api/v3/predictions/{task_id}/result"
        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)
            pr = await client.get(result_url, headers={"Authorization": headers["Authorization"]})
            if pr.status_code >= 400:
                log.warning("wavespeed video poll %s: %s", pr.status_code, (pr.text or "")[:800])
                continue
            try:
                raw_poll = pr.json()
            except Exception:
                continue
            if not isinstance(raw_poll, dict):
                continue
            penv = _wavespeed_envelope_error(raw_poll)
            if penv:
                log.warning("wavespeed video poll envelope: %s", penv)
                raise RuntimeError(f"WaveSpeed: {penv}")
            pd = _unwrap_data(raw_poll)
            st = (pd.get("status") or "").lower()
            if st == "failed":
                raise RuntimeError(str(pd.get("error") or "WaveSpeed task failed"))
            if st == "completed":
                u = _video_url_from_prediction(pd)
                if u:
                    return u
                raise RuntimeError(
                    str(
                        pd.get("error")
                        or "WaveSpeed: задача completed, но нет URL видео"
                    )
                )
            u = _video_url_from_prediction(pd)
            if u:
                return u
    raise RuntimeError("WaveSpeed: timeout waiting for video")


def _wan_22_animate_post_path() -> str:
    p = (settings.wavespeed_wan_22_animate_path or "").strip()
    p = p or "/api/v3/wavespeed-ai/wan-2.2/animate"
    return p if p.startswith("/") else f"/{p}"


async def wan_22_animate_video_url(
    *,
    api_key: str,
    image_url: str,
    video_url: str,
    prompt: str | None = None,
    mode: str | None = None,
    resolution: str | None = None,
    seed: int | None = None,
    timeout_submit: float = 900.0,
    poll_interval: float = 3.0,
    max_polls: int = 180,
) -> str:
    """
    WAN 2.2 Animate: image + driving video → video. Режим replace/animate.
    Док: https://wavespeed.ai/docs/docs-api/wavespeed-ai/wan-2.2-animate
    """
    img = (image_url or "").strip()
    vid = (video_url or "").strip()
    if not img or not vid:
        raise RuntimeError("image and video URLs required")
    m = (mode or settings.wavespeed_wan_22_animate_mode or "replace").strip().lower()
    if m not in ("animate", "replace"):
        raise RuntimeError('WAN 2.2 Animate: mode must be "animate" or "replace"')
    res = (resolution or settings.wavespeed_wan_22_animate_resolution or "720p").strip()
    if res not in ("480p", "720p"):
        res = "720p"
    path = _wan_22_animate_post_path()
    url = f"{_wavespeed_base()}{path}"
    body: dict[str, Any] = {
        "image": img,
        "video": vid,
        "mode": m,
        "resolution": res,
        "seed": int(seed if seed is not None else settings.wavespeed_wan_22_animate_seed),
    }
    ptxt = (prompt or "").strip()
    if ptxt:
        body["prompt"] = ptxt
    _apply_wavespeed_extra_body(body)
    log.debug("wavespeed wan 2.2 animate path=%s mode=%s resolution=%s", path, m, res)
    return await _wavespeed_post_json_and_resolve_video_url(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )


def _seedance_20_t2v_post_path(*, variant: str = "standard") -> str:
    from app.services.studio_motion_pricing import normalize_seedance_t2v_variant

    v = normalize_seedance_t2v_variant(variant)
    if v == "mini":
        p = (settings.wavespeed_seedance_20_mini_t2v_path or "").strip()
        p = p or "/api/v3/bytedance/seedance-2.0-mini/text-to-video"
    else:
        p = (settings.wavespeed_seedance_20_t2v_path or "").strip()
        p = p or "/api/v3/bytedance/seedance-2.0/text-to-video"
    return p if p.startswith("/") else f"/{p}"


async def seedance_20_text_to_video_url(
    *,
    api_key: str,
    prompt: str,
    reference_images: list[str] | None = None,
    reference_videos: list[str] | None = None,
    reference_audios: list[str] | None = None,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    duration: int | None = None,
    generate_audio: bool = True,
    enable_web_search: bool | None = None,
    variant: str = "standard",
    timeout_submit: float = 900.0,
    poll_interval: float = 3.0,
    max_polls: int = 180,
) -> str:
    """
    ByteDance Seedance 2.0 Text-to-Video: prompt + reference_images (@ImageN в тексте).
    variant=standard → …/seedance-2.0/text-to-video
    variant=mini → …/seedance-2.0-mini/text-to-video
    Док: https://wavespeed.ai/docs/docs-api/bytedance/bytedance-seedance-2.0-text-to-video
    """
    if not (prompt or "").strip():
        raise RuntimeError("prompt required for text-to-video")
    from app.services.studio_motion_pricing import normalize_seedance_t2v_resolution

    res = normalize_seedance_t2v_resolution(
        resolution or settings.wavespeed_seedance_20_t2v_resolution
    )
    from app.services.studio_motion_pricing import motion_video_duration_seconds

    dur = motion_video_duration_seconds(
        duration if duration is not None else None,
        default=settings.wavespeed_seedance_20_t2v_duration,
    )
    path = _seedance_20_t2v_post_path(variant=variant)
    url = f"{_wavespeed_base()}{path}"
    body: dict[str, Any] = {
        "prompt": prompt.strip(),
        "resolution": res,
        "duration": dur,
        "enable_web_search": bool(
            enable_web_search
            if enable_web_search is not None
            else settings.wavespeed_seedance_20_t2v_web_search
        ),
        "generate_audio": bool(generate_audio),
    }
    ar = (aspect_ratio or "").strip()
    if ar:
        body["aspect_ratio"] = ar
    imgs = [u.strip() for u in (reference_images or []) if (u or "").strip()]
    if imgs:
        body["reference_images"] = imgs[:9]
    vids = [u.strip() for u in (reference_videos or []) if (u or "").strip()]
    if vids:
        body["reference_videos"] = vids[:3]
    auds = [u.strip() for u in (reference_audios or []) if (u or "").strip()]
    if auds:
        body["reference_audios"] = auds[:3]
    _apply_wavespeed_extra_body(body)
    log.debug(
        "wavespeed seedance t2v variant=%s path=%s res=%s dur=%s imgs=%s vids=%s",
        variant,
        path,
        res,
        dur,
        len(body.get("reference_images") or []),
        len(body.get("reference_videos") or []),
    )
    return await _wavespeed_post_json_and_resolve_video_url(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=settings.wavespeed_video_poll_interval_seconds,
        max_polls=settings.wavespeed_video_max_polls,
    )


def _seedance_20_i2v_post_path() -> str:
    p = (settings.wavespeed_seedance_20_i2v_path or "").strip()
    p = p or "/api/v3/bytedance/seedance-2.0/image-to-video"
    return p if p.startswith("/") else f"/{p}"


async def seedance_20_image_to_video_url(
    *,
    api_key: str,
    image_url: str,
    prompt: str,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    duration: int | None = None,
    generate_audio: bool = True,
    timeout_submit: float = 900.0,
    poll_interval: float = 3.0,
    max_polls: int = 180,
) -> str:
    """
    ByteDance Seedance 2.0 Image-to-Video: стартовый кадр + prompt → видео.
    Док: https://wavespeed.ai/docs/docs-api/bytedance/bytedance-seedance-2.0-image-to-video
    """
    img = (image_url or "").strip()
    if not img:
        raise RuntimeError("image URL required")
    if not (prompt or "").strip():
        raise RuntimeError("prompt required for image-to-video")
    res = (resolution or settings.wavespeed_seedance_20_i2v_resolution or "720p").strip().lower()
    if res not in ("480p", "720p", "1080p"):
        res = "720p"
    from app.services.studio_motion_pricing import motion_video_duration_seconds

    dur = motion_video_duration_seconds(
        duration if duration is not None else None,
        default=settings.wavespeed_seedance_20_i2v_duration,
    )
    path = _seedance_20_i2v_post_path()
    url = f"{_wavespeed_base()}{path}"
    body: dict[str, Any] = {
        "prompt": prompt.strip(),
        "image": img,
        "resolution": res,
        "duration": dur,
        "enable_web_search": bool(settings.wavespeed_seedance_20_i2v_web_search),
        "generate_audio": bool(generate_audio),
    }
    ar = (aspect_ratio or "").strip()
    if ar:
        body["aspect_ratio"] = ar
    _apply_wavespeed_extra_body(body)
    log.debug(
        "wavespeed seedance 2.0 i2v path=%s res=%s dur=%s aspect=%s audio=%s",
        path,
        res,
        dur,
        ar or "(auto)",
        generate_audio,
    )
    return await _wavespeed_post_json_and_resolve_video_url(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )


def _grok_imagine_video_v15_i2v_post_path() -> str:
    p = (settings.wavespeed_grok_imagine_video_v15_i2v_path or "").strip()
    p = p or "/api/v3/x-ai/grok-imagine-video-v1.5/image-to-video"
    return p if p.startswith("/") else f"/{p}"


async def grok_imagine_video_v15_image_to_video_url(
    *,
    api_key: str,
    image_url: str,
    prompt: str,
    resolution: str | None = None,
    duration: int | None = None,
    timeout_submit: float = 900.0,
    poll_interval: float = 3.0,
    max_polls: int = 180,
) -> str:
    """
    xAI Grok Imagine Video v1.5 Image-to-Video: стартовый кадр + prompt → видео.
    Док: https://wavespeed.ai/models/x-ai/grok-imagine-video-v1.5/image-to-video
    """
    from app.services.studio_motion_pricing import (
        grok_imagine_i2v_duration_seconds,
        normalize_grok_imagine_i2v_resolution,
    )

    img = (image_url or "").strip()
    if not img:
        raise RuntimeError("image URL required")
    if not (prompt or "").strip():
        raise RuntimeError("prompt required for image-to-video")
    res = normalize_grok_imagine_i2v_resolution(resolution)
    dur = grok_imagine_i2v_duration_seconds(
        duration if duration is not None else None,
        default=6,
    )
    path = _grok_imagine_video_v15_i2v_post_path()
    url = f"{_wavespeed_base()}{path}"
    body: dict[str, Any] = {
        "prompt": prompt.strip(),
        "image": img,
        "resolution": res,
        "duration": dur,
    }
    _apply_wavespeed_extra_body(body)
    log.debug(
        "wavespeed grok imagine video v1.5 i2v path=%s res=%s dur=%s",
        path,
        res,
        dur,
    )
    return await _wavespeed_post_json_and_resolve_video_url(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )


def _studio_video_edit_post_path() -> str:
    p = (settings.wavespeed_studio_video_edit_path or "").strip()
    p = p or "/api/v3/bytedance/seedance-2.0-fast/video-edit-turbo"
    return p if p.startswith("/") else f"/{p}"


async def seedance_studio_video_edit_video_url(
    *,
    api_key: str,
    video_url: str,
    reference_image_url: str | None = None,
    reference_image_urls: list[str] | None = None,
    prompt: str,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    duration: int | None = None,
    keep_original_sound: bool = True,
    timeout_submit: float = 900.0,
    poll_interval: float = 3.0,
    max_polls: int = 180,
) -> str:
    """
    ByteDance Seedance (Fast) Video-Edit Turbo: входное видео + промпт + reference_images.
    Док: https://wavespeed.ai/docs/docs-api/bytedance/bytedance-seedance-2.0-video-edit-turbo
    """
    vid = (video_url or "").strip()
    ptxt = (prompt or "").strip()
    if not vid:
        raise RuntimeError("video URL required for video edit")
    if not ptxt:
        raise RuntimeError("prompt required for video edit")
    imgs: list[str] = []
    if reference_image_urls:
        imgs = [u.strip() for u in reference_image_urls if (u or "").strip()]
    elif reference_image_url:
        imgs = [(reference_image_url or "").strip()]
    if not imgs:
        raise RuntimeError("reference image URLs required for video edit")
    path = _studio_video_edit_post_path()
    url = f"{_wavespeed_base()}{path}"
    res = (resolution or settings.wavespeed_studio_video_edit_resolution or "720p").strip()
    body: dict[str, Any] = {
        "prompt": ptxt,
        "video": vid,
        "reference_images": imgs[:9],
        "resolution": res,
        "enable_web_search": False,
        # false = сохранить звуковую дорожку входного видео; true = сгенерировать новое аудио
        "generate_audio": not bool(keep_original_sound),
    }
    if duration is not None:
        from app.services.studio_motion_pricing import motion_video_duration_seconds

        body["duration"] = motion_video_duration_seconds(duration)
    ar = (aspect_ratio or "").strip()
    if ar:
        body["aspect_ratio"] = ar
    _apply_wavespeed_extra_body(body)
    log.debug(
        "wavespeed studio video edit path=%s resolution=%s imgs=%s dur=%s",
        path,
        res,
        len(body["reference_images"]),
        body.get("duration"),
    )
    return await _wavespeed_post_json_and_resolve_video_url(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=settings.wavespeed_video_poll_interval_seconds,
        max_polls=settings.wavespeed_video_max_polls,
    )


def _kling_motion_control_post_path() -> str:
    p = (settings.wavespeed_kling_motion_control_path or "").strip()
    p = p or "/api/v3/kwaivgi/kling-v3.0-pro/motion-control"
    return p if p.startswith("/") else f"/{p}"


async def kling_motion_control_video_url(
    *,
    api_key: str,
    image_url: str,
    video_url: str,
    character_orientation: str,
    prompt: str = "",
    negative_prompt: str = "",
    keep_original_sound: bool = True,
    timeout_submit: float = 900.0,
    poll_interval: float = 3.0,
    max_polls: int = 180,
) -> str:
    """Kling V3 Pro Motion Control: character image + driving video → output video URL."""
    img = (image_url or "").strip()
    vid = (video_url or "").strip()
    if not img or not vid:
        raise RuntimeError("image and video URLs required")
    orient = (character_orientation or "video").strip().lower()
    if orient not in ("image", "video"):
        raise RuntimeError("character_orientation must be image or video")
    path = _kling_motion_control_post_path()
    url = f"{_wavespeed_base()}{path}"
    body: dict[str, Any] = {
        "image": img,
        "video": vid,
        "character_orientation": orient,
        "keep_original_sound": bool(keep_original_sound),
        "enable_sync_mode": bool(settings.wavespeed_kling_motion_sync),
        "enable_base64_output": False,
    }
    ptxt = (prompt or "").strip()
    if ptxt:
        body["prompt"] = ptxt
    ntxt = (negative_prompt or "").strip()
    if ntxt:
        body["negative_prompt"] = ntxt
    _apply_wavespeed_extra_body(body)
    log.debug(
        "wavespeed kling motion path=%s orient=%s sync=%s",
        path,
        orient,
        settings.wavespeed_kling_motion_sync,
    )
    return await _wavespeed_post_json_and_resolve_video_url(
        api_key=api_key,
        full_post_url=url,
        body=body,
        timeout_submit=timeout_submit,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )
