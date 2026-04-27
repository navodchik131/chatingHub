from __future__ import annotations

import base64
import json
import logging
import re

import httpx

from app.config import BACKEND_DIR, settings
from app.services.studio_aspect import aspect_user_block_english

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 12 * 1024 * 1024


def _openai_friendly_error(message: str, status_code: int) -> RuntimeError:
    m = (message or "").strip()
    low = m.lower()
    if "something went wrong" in low or "please try again" in low:
        m = (
            f"{m} — типично это временная ошибка API OpenAI (HTTP {status_code}). "
            "Повторите позже, проверьте статус: https://status.openai.com и лимиты/баланс в кабинете."
        )
    return RuntimeError(m)


def load_image_studio_skeleton() -> str:
    path = (BACKEND_DIR / settings.image_studio_skeleton_path).resolve()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return (settings.image_studio_skeleton_inline or "").strip()


def load_image_studio_system() -> str:
    path = (BACKEND_DIR / settings.image_studio_system_path).resolve()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return (settings.image_studio_system_inline or "").strip()


def load_canonical_realism_engine() -> dict | None:
    if (settings.image_studio_realism_engine_inline or "").strip():
        try:
            data = json.loads(settings.image_studio_realism_engine_inline)
        except json.JSONDecodeError:
            return None
    else:
        path = (BACKEND_DIR / settings.image_studio_realism_engine_path).resolve()
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    if isinstance(data, dict) and "realism_engine" in data and isinstance(
        data["realism_engine"], dict
    ):
        return data["realism_engine"]
    return data if isinstance(data, dict) else None


def prepare_studio_prompt_skeleton() -> str:
    """Скелет с подставленным из файла realism_engine; при ошибке разбора — сырой текст."""
    raw = load_image_studio_skeleton()
    if not raw.strip():
        return ""
    re_obj = load_canonical_realism_engine()
    if re_obj is None:
        return raw
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("studio skeleton: invalid JSON, using raw: %s", e)
        return raw
    if not isinstance(data, dict):
        return raw
    data["realism_engine"] = re_obj
    return json.dumps(data, ensure_ascii=False, indent=2)


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t, flags=re.DOTALL)
    return t.strip()


def apply_canonical_realism_to_refined_output(text: str) -> str:
    """После LLM: зафиксировать realism_engine из канонического JSON."""
    re_obj = load_canonical_realism_engine()
    if re_obj is None:
        return text
    raw = _strip_code_fences(text)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        log.warning("refined output: not valid JSON, skip realism merge: %s", e)
        return text
    if not isinstance(data, dict):
        return text
    data["realism_engine"] = re_obj
    return json.dumps(data, ensure_ascii=False, indent=2)


def load_reference_describe_prompt() -> str:
    path = (BACKEND_DIR / settings.image_studio_reference_describe_path).resolve()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return (settings.image_studio_reference_describe_inline or "").strip()


async def _chat_completion_text(
    *,
    model: str,
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.65,
) -> str:
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise RuntimeError("openai not configured")

    base = (settings.openai_base_url or "").strip().rstrip("/")
    if not base:
        base = "https://api.openai.com/v1"
    url = f"{base}/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req_headers: dict[str, str] = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    org = (settings.openai_organization or "").strip()
    if org:
        req_headers["OpenAI-Organization"] = org

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=req_headers, json=payload)
        req_id = (r.headers.get("x-request-id") or r.headers.get("openai-request-id") or "").strip()

    if r.status_code >= 400:
        err_body = (r.text or "")[:1500]
        log.warning(
            "openai request failed: %s %s request_id=%s url=%s",
            r.status_code,
            err_body,
            req_id or "—",
            url,
        )
        try:
            ej = r.json()
            if isinstance(ej, dict):
                err = ej.get("error")
                if isinstance(err, dict) and err.get("message"):
                    msg = str(err["message"])
                    if req_id and "request id" not in msg.lower():
                        msg = f"{msg} (OpenAI request_id: {req_id})"
                    raise _openai_friendly_error(msg, r.status_code)
                if isinstance(err, str):
                    raise _openai_friendly_error(err, r.status_code)
        except RuntimeError:
            raise
        except Exception:
            pass
        raise RuntimeError(
            f"OpenAI HTTP {r.status_code}"
            + (f" (request_id: {req_id})" if req_id else "")
            + ". Проверьте OPENAI_API_KEY, лимиты и https://status.openai.com"
        )

    data = r.json()
    try:
        out = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        log.warning("openai bad response: %s", data)
        raise RuntimeError("OpenAI response shape unexpected") from e
    text = (out or "").strip()
    if not text:
        raise RuntimeError("OpenAI returned empty content")
    return text


async def describe_reference_image_openai(
    *,
    image_bytes: bytes,
    image_media_type: str | None,
) -> str:
    """Шаг 1: только визуальное описание референса (поза, одежда, сцена), без финального JSON."""
    instruction = load_reference_describe_prompt()
    if not instruction:
        raise RuntimeError(
            "Текст запроса для описания референса пуст — задайте файл "
            "data/prompts/image_studio_reference_describe.txt или "
            "IMAGE_STUDIO_REFERENCE_DESCRIBE_INLINE"
        )

    model = (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    mime = (image_media_type or "image/jpeg").split(";")[0].strip()
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"

    system = (
        "You follow instructions precisely. Output only the requested English description, "
        "no preamble, no markdown, no labels."
    )
    user_content: list[dict] = [
        {"type": "text", "text": instruction},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        },
    ]

    return await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        max_tokens=2048,
        temperature=0.4,
    )


def _build_refiner_user_message(
    *,
    skeleton: str,
    user_text: str,
    reference_scene_description: str | None,
    model_profile_text: str | None,
    output_aspect_key: str,
) -> str:
    blocks: list[str] = []
    blocks.append("## SKELETON (JSON template: fill <FILL…>, map <FROM_MODEL_PROFILE> from MODEL_PROFILE)")
    blocks.append(skeleton.strip())
    blocks.append("## MODEL_PROFILE (identity — use for <FROM_MODEL_PROFILE>; if JSON, copy literally)")
    if model_profile_text and model_profile_text.strip():
        blocks.append(model_profile_text.strip())
    else:
        blocks.append(
            "(no model selected — use neutral, minimal identity only where required, or keep placeholders specific only to USER_TEXT)"
        )
    if reference_scene_description and reference_scene_description.strip():
        blocks.append(
            "## REFERENCE_IMAGE (pose, clothing, framing, environment, lighting only — do NOT use face/identity from image)\n"
            + reference_scene_description.strip()
        )
    else:
        blocks.append("## REFERENCE_IMAGE\n(none — no input reference image)")
    u = (user_text or "").strip()
    blocks.append("## USER_TEXT (primary scene and intent)\n" + (u if u else "(no additional text)"))
    blocks.append(aspect_user_block_english(output_aspect_key))
    return "\n\n".join(blocks)


async def refine_prompt_via_openai(
    *,
    system_instruction: str,
    skeleton: str,
    user_text: str,
    reference_scene_description: str | None,
    model_profile_text: str | None,
    output_aspect_key: str,
) -> str:
    """Шаг 2: одна сессия чата — system = инструкция, user = шаблон + данные; ответ: JSON-строка."""
    if not (system_instruction or "").strip():
        raise RuntimeError("image studio: empty system instruction")
    model = settings.openai_studio_model
    user_message = _build_refiner_user_message(
        skeleton=skeleton,
        user_text=user_text,
        reference_scene_description=reference_scene_description,
        model_profile_text=model_profile_text,
        output_aspect_key=output_aspect_key,
    )
    raw = await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system_instruction.strip()},
            {"role": "user", "content": user_message},
        ],
        max_tokens=8192,
        temperature=0.55,
    )
    return apply_canonical_realism_to_refined_output(raw)
