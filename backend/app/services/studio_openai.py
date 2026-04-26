from __future__ import annotations

import base64
import logging

import httpx

from app.config import BACKEND_DIR, settings
from app.services.studio_aspect import aspect_instruction_for_prompt

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


def _build_second_stage_user_message(
    *,
    user_text: str,
    reference_scene_description: str | None,
    model_profile_text: str | None,
    output_aspect_instruction: str | None,
) -> str:
    blocks: list[str] = []
    if output_aspect_instruction and output_aspect_instruction.strip():
        blocks.append(output_aspect_instruction.strip())
    if model_profile_text and model_profile_text.strip():
        blocks.append(
            "Профиль выбранной модели (используй для внешности, возраста, волос, кожи и т.д. в JSON):\n"
            + model_profile_text.strip()
        )
    if reference_scene_description and reference_scene_description.strip():
        blocks.append(
            "Описание с референс-фото (поза, руки, одежда, окружение, ракурс, атмосфера — "
            "не подменяй профиль модели чужим лицом с фото):\n"
            + reference_scene_description.strip()
        )
    ut = (user_text or "").strip()
    if ut:
        blocks.append("Пожелания пользователя:\n" + ut)
    if not blocks:
        return "Собери финальный JSON строго по шаблону из системного сообщения."
    return "\n\n".join(blocks)


async def refine_prompt_via_openai(
    *,
    skeleton: str,
    user_text: str,
    reference_scene_description: str | None,
    model_profile_text: str | None,
    output_aspect_key: str,
) -> str:
    """Шаг 2: только текст — собрать итоговый JSON по скелету."""
    model = settings.openai_studio_model

    system_content = (
        "Ты собираешь финальный промпт в виде одного JSON-объекта строго по правилам и примеру ниже.\n"
        "Верни только JSON, без markdown и без пояснений до или после.\n\n"
        "--- Шаблон и правила ---\n"
        f"{skeleton}\n"
        "--- Конец шаблона ---"
    )

    user_message = _build_second_stage_user_message(
        user_text=user_text,
        reference_scene_description=reference_scene_description,
        model_profile_text=model_profile_text,
        output_aspect_instruction=aspect_instruction_for_prompt(output_aspect_key),
    )

    return await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_message},
        ],
        max_tokens=8192,
        temperature=0.55,
    )
