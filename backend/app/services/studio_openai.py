from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import BACKEND_DIR, settings
from app.services.studio_aspect import aspect_user_block_english

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True)
class StudioOpenAiCredentials:
    api_key: str
    base_url: str
    organization: str = ""


def _wavespeed_pose_ref_prefix(*, lock_model_hairstyle: bool) -> str:
    hair_clause = (
        "**Hairstyle (braids, loose, bun, etc.) follows the JSON brief / model identity — not this image.** "
        if lock_model_hairstyle
        else "hair styling as in that shot, "
    )
    return (
        "[REFERENCE_IMAGE_ORDER] The first image is the user's uploaded pose/scene reference. "
        "Take from it: pose articulation (hands, limbs), camera angle/height/distance, framing, lens feel, "
        f"{hair_clause}"
        "background and lighting. "
        "Garments and body coverage must match only this first image — do not dress the subject from the "
        "other images. If the first image shows no clothing or partial nudity, keep the same coverage (nude/topless/etc.). "
        "**Do not do a face-swap:** synthesize **one cohesive person** in this scene. Silhouette, proportions, and **all visible skin** "
        "(face, neck, chest, arms, torso, legs) must match the identity reference images (following URLs) continuously — same tone, "
        "same texture grain, lighting falling the same way on face and body; not a sharp face on a mismatched body. "
        "Following image(s): the saved model only for **who** this person is (face + body identity); "
        "**never** copy pose, camera, framing, or outfit from those images — those come only from the first image.\n\n"
    )


def wavespeed_prompt_with_user_pose_reference_first(
    refined_prompt: str,
    *,
    lock_model_hairstyle: bool = True,
) -> str:
    """Префикс к финальному промпту WaveSpeed, когда первый URL — загруженный пользователем референс."""
    prefix = _wavespeed_pose_ref_prefix(lock_model_hairstyle=lock_model_hairstyle)
    p = (refined_prompt or "").strip()
    if not p:
        return prefix.strip()
    return prefix + p


_WAVESPEED_PHOTO_EDIT_USER_FIRST_PREFIX = (
    "[EDIT_BASE] The first image is the user's photograph to edit. "
    "Apply the JSON scene/instruction as modifications to this image (lighting, background, wardrobe, pose tweaks, cleanup) while keeping "
    "the same person as the base **throughout** — continuous skin, lighting, and anatomy; avoid a pasted-on face look. "
    "If further images follow, they are optional model references — use for **full-body** identity (skin, face, proportions) when the edit "
    "needs them; do not replace the first image's person with a composite head.\n\n"
)

_WAVESPEED_NO_FACE_SUFFIX = (
    "\n\n[FRAMING] Do not show the subject's face or head unless the scene explicitly requires it. "
    "Prefer crops on legs, feet, lower body, hands, or torso without head. "
    "Do not add, restore, or reconstruct a face."
)


def finalize_wavespeed_studio_prompt(
    refined_prompt: str,
    *,
    studio_mode: str,
    user_image_first: bool,
    lock_model_hairstyle: bool = True,
) -> str:
    """Сборка финального текстового промпта для WaveSpeed в зависимости от режима студии."""
    mode = (studio_mode or "model").strip().lower()
    p = (refined_prompt or "").strip()
    if user_image_first:
        if mode == "photo_edit":
            out = (
                _WAVESPEED_PHOTO_EDIT_USER_FIRST_PREFIX.strip()
                if not p
                else _WAVESPEED_PHOTO_EDIT_USER_FIRST_PREFIX + p
            )
        else:
            out = wavespeed_prompt_with_user_pose_reference_first(
                p, lock_model_hairstyle=lock_model_hairstyle
            )
    else:
        out = p
    if mode == "no_face":
        out = (out or "").rstrip() + _WAVESPEED_NO_FACE_SUFFIX
    return out


_NANO_BANANA_IDENTITY_LOCK_PREFIX = (
    "[MULTI_IMAGE_EDIT — same person] The first input image(s) are reference photos of ONE real person "
    "for **identity only**: face, facial structure, eyes, nose, mouth, skin tone, hairline, hair, and body "
    "proportions/shape. Do **not** use those images as the source of **pose, camera angle, focal length, "
    "framing/crop, background layout, outfit, or scene lighting** — the JSON brief (and the **last** input "
    "image when present) define composition and wardrobe. "
    "The output MUST preserve identity from these references — do not invent a different person or a generic model face. "
    "The block below is a structured scene brief (JSON); identity always wins over any vague text.\n\n"
)

def _nano_banana_pose_last_suffix(*, lock_model_hairstyle: bool) -> str:
    hair = (
        "**Hairstyle must follow the JSON brief (model identity), not the hair layout on this last image.** "
        if lock_model_hairstyle
        else "**Hairstyle may match the last (pose) image when the JSON says POSE_REFERENCE.** "
    )
    return (
        "\n\n[LAST_INPUT_IMAGE] The **last** input image is the **only** source for **pose, framing, camera geometry, "
        "outfit/body coverage, background, and environmental lighting** in this edit. "
        + hair
        + "Ignore any face or skin on that last image — the subject must match only the earlier identity reference image(s). "
        "Do not blend the pose or shot type from the identity images above."
    )


def finalize_nano_banana_studio_prompt(
    refined_prompt: str,
    *,
    studio_mode: str,
    user_photo_edit_first: bool,
    user_pose_reference_is_last: bool,
    lock_model_hairstyle: bool = True,
) -> str:
    """
    Nano Banana Pro: порядок URL другой, чем у WAN (сначала лицо модели, поза пользователя — в конце).
    user_photo_edit_first: «Доработать фото» — первое фото = база для правок (порядок не меняли).
    user_pose_reference_is_last: после reorder загруженный референс позы — последний кадр в списке.
    """
    mode = (studio_mode or "model").strip().lower()
    p = (refined_prompt or "").strip()

    if user_photo_edit_first and mode == "photo_edit":
        out = (
            _WAVESPEED_PHOTO_EDIT_USER_FIRST_PREFIX.strip()
            if not p
            else _WAVESPEED_PHOTO_EDIT_USER_FIRST_PREFIX + p
        )
    else:
        head = _NANO_BANANA_IDENTITY_LOCK_PREFIX
        out = head.strip() if not p else head + p
        if user_pose_reference_is_last:
            out = out.rstrip() + _nano_banana_pose_last_suffix(
                lock_model_hairstyle=lock_model_hairstyle
            )

    if mode == "no_face":
        out = (out or "").rstrip() + _WAVESPEED_NO_FACE_SUFFIX
    return out


# Если .env задал пустой путь или на сервере нет data/prompts — не падаем с 503.
_DEFAULT_IMAGE_STUDIO_SYSTEM = """
You are a prompt builder for the WAN 2.7 Image Edit model.

You will receive:
1. A SKELETON (JSON template with <FILL> and <FROM_MODEL_PROFILE>).
2. Optional REFERENCE_IMAGE — when not "(none)", it is the source of truth for **scene layout, camera geometry, and clothing/coverage** (pose, hands, framing/crop, camera distance and height, angle, lens feel, background, lighting).
3. A MODEL PROFILE — **identity** only (face, skin, hair, body type as character); not a replacement for the reference scene.
4. USER_TEXT, 5. OUTPUT/ASPECT.

If REFERENCE_IMAGE has content: fill pose, clothing (only what the reference photo shows; if none — nude/uncovered), photography, background from the reference, not from profile defaults. The user message has `## HAIRSTYLE_MODE`: **MODEL_LOCK** = `hair_in_scene` from MODEL_PROFILE; **POSE_REFERENCE** = `hair_in_scene` from the reference. Never take clothing from MODEL_PROFILE. **Always take face, body_type, skin tone; hair color + identity baseline from MODEL_PROFILE** — never mimic the reference person's skin. **Synthesize one coherent person**. MODEL_PROFILE fills <FROM_MODEL_PROFILE>; no reference face or body copy.
**Consistency:** camera_style + camera_distance + framing + shot_type + hands must be physically possible (no front-camera "selfie" at 1–2 m full body without mirror/tripod/friend). clothing.imperfections must not contradict realism_engine fabric_realism. Keep realism_engine exactly as in the skeleton. Output only valid JSON, no markdown.
""".strip()


def _relative_prompt_path(val: str, default_rel: str) -> str:
    v = (val or "").strip()
    return v if v else default_rel


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
    rel = _relative_prompt_path(
        settings.image_studio_skeleton_path,
        "data/prompts/image_studio_skeleton.txt",
    )
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return (settings.image_studio_skeleton_inline or "").strip()


def load_image_studio_system() -> str:
    rel = _relative_prompt_path(
        settings.image_studio_system_path,
        "data/prompts/image_studio_system.txt",
    )
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file():
        t = path.read_text(encoding="utf-8").strip()
        if t:
            return t
    inline = (settings.image_studio_system_inline or "").strip()
    if inline:
        return inline
    log.warning(
        "image_studio_system: file missing or empty (%s), using built-in default",
        path,
    )
    return _DEFAULT_IMAGE_STUDIO_SYSTEM


def _realism_engine_dict_for_prompt(raw: dict) -> dict:
    """Убрать служебные ключи (_comment и т.д.), чтобы JSON для модели не зашумлять."""
    return {k: v for k, v in raw.items() if isinstance(k, str) and not k.startswith("_")}


def load_canonical_realism_engine() -> dict | None:
    if (settings.image_studio_realism_engine_inline or "").strip():
        try:
            data = json.loads(settings.image_studio_realism_engine_inline)
        except json.JSONDecodeError:
            return None
    else:
        rel = _relative_prompt_path(
            settings.image_studio_realism_engine_path,
            "data/prompts/image_studio_realism_engine.json",
        )
        path = (BACKEND_DIR / rel).resolve()
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    inner: dict | None = None
    if isinstance(data, dict) and "realism_engine" in data and isinstance(
        data["realism_engine"], dict
    ):
        inner = data["realism_engine"]
    elif isinstance(data, dict):
        inner = data
    if inner is None:
        return None
    return _realism_engine_dict_for_prompt(inner)


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


def load_reference_describe_prompt(*, hairstyle_from_pose_reference: bool = False) -> str:
    if hairstyle_from_pose_reference:
        rel = _relative_prompt_path(
            settings.image_studio_reference_describe_match_pose_hair_path,
            "data/prompts/image_studio_reference_describe_match_pose_hair.txt",
        )
    else:
        rel = _relative_prompt_path(
            settings.image_studio_reference_describe_path,
            "data/prompts/image_studio_reference_describe.txt",
        )
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file():
        t = path.read_text(encoding="utf-8").strip()
        if t:
            return t
    if hairstyle_from_pose_reference:
        log.warning(
            "reference describe (pose hair): file missing or empty (%s), using standard describe prompt",
            path,
        )
        return load_reference_describe_prompt(hairstyle_from_pose_reference=False)
    return (settings.image_studio_reference_describe_inline or "").strip()


async def _chat_completion_text(
    *,
    model: str,
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.65,
    credentials: StudioOpenAiCredentials | None = None,
) -> str:
    cred = credentials
    if cred is None:
        key = (settings.openai_api_key or "").strip()
        if not key:
            raise RuntimeError("openai not configured")
        base = (settings.openai_base_url or "").strip().rstrip("/")
        if not base:
            base = "https://api.openai.com/v1"
        org = (settings.openai_organization or "").strip()
    else:
        key = cred.api_key.strip()
        if not key:
            raise RuntimeError("openai not configured")
        base = cred.base_url.strip().rstrip("/")
        if not base:
            base = "https://api.openai.com/v1"
        org = (cred.organization or "").strip()

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
    hairstyle_from_pose_reference: bool = False,
    credentials: StudioOpenAiCredentials | None = None,
) -> str:
    """Шаг 1: только визуальное описание референса (поза, одежда, сцена), без финального JSON."""
    instruction = load_reference_describe_prompt(
        hairstyle_from_pose_reference=hairstyle_from_pose_reference,
    )
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
        credentials=credentials,
    )


def _studio_mode_refiner_block(studio_mode: str) -> str:
    m = (studio_mode or "model").strip().lower()
    if m == "photo_edit":
        return (
            "## STUDIO_MODE: PHOTO_EDIT\n"
            "Treat the REFERENCE_IMAGE (when present) as the primary photograph to edit. "
            "Fill the skeleton so the result reflects USER_TEXT changes applied to that photo. "
            "MODEL_PROFILE (if any) refines visible identity cues only when the edit requires them — "
            "do not replace the uploaded person's face with the model's unless USER_TEXT asks.\n"
        )
    if m == "no_face":
        return (
            "## STUDIO_MODE: NO_FACE_FRAMING\n"
            "Final image must NOT show the subject's face or head unless USER_TEXT explicitly requires a face. "
            "Prefer legs/feet/hands/lower-body/torso-below-shoulders framing consistent with references. "
            "In subject.identity, omit or minimize facial detail; never invent or restore a face.\n"
        )
    return ""


def _build_refiner_user_message(
    *,
    skeleton: str,
    user_text: str,
    reference_scene_description: str | None,
    model_profile_text: str | None,
    output_aspect_key: str,
    studio_mode: str = "model",
    lock_model_hairstyle: bool = True,
) -> str:
    has_ref = bool((reference_scene_description or "").strip())
    mode_line = "MODEL_LOCK" if lock_model_hairstyle else "POSE_REFERENCE"
    blocks: list[str] = [
        "## HAIRSTYLE_MODE\n" + mode_line,
        "## SKELETON (JSON template: fill <FILL…>, <FROM_MODEL_PROFILE> from model profile, <FILL_FROM_IMAGE_OR_TEXT> from reference when present)",
        skeleton.strip(),
    ]

    # Референс — сразу после скелета, чтобы сцена не утонула в длинном JSON профиля.
    if has_ref:
        if lock_model_hairstyle:
            ref_intro = (
                "## REFERENCE_IMAGE (scene/pose ref only: pose/hands, clothing/coverage on this photo, camera/framing/light/room — "
                "**not** hairstyle; **not** body type, skin tone, or face; those = MODEL_PROFILE). "
            )
        else:
            ref_intro = (
                "## REFERENCE_IMAGE (scene/pose ref: pose/hands, clothing/coverage, **hair styling in this shot**, "
                "camera/framing/light/room — **not** body type, skin tone, or face; those = MODEL_PROFILE). "
            )
        blocks.append(
            ref_intro
            + "**Render as one person:** fill JSON so the edit model **re-synthesizes the full body** of MODEL_PROFILE in this pose and room — not face-only over the reference sitter's body.\n"
            + (reference_scene_description or "").strip()
        )
    else:
        blocks.append("## REFERENCE_IMAGE\n(none — no input reference image)")

    if lock_model_hairstyle:
        blocks.append(
            "## MODEL_PROFILE (identity: face, skin, hair color **and hairstyle**, body type, marks — for <FROM_MODEL_PROFILE> and **`hair_in_scene`**. "
            "If REFERENCE_IMAGE exists: **never** use profile for clothing or accessories — only the reference photo + USER_TEXT. "
            "**Always** use profile for `subject.identity` (face, skin tone, body_type, hair color, hair style, marks) and for **`hair_in_scene`** "
            "**for every visible body part** — one continuous person. Do not copy default outfit/jewelry/posture/scene from profile over the reference layout "
            "**except hairstyle**, which always follows the profile unless USER_TEXT explicitly changes it.)"
        )
    else:
        blocks.append(
            "## MODEL_PROFILE (identity: face, skin, hair color, body type, marks — for `subject.identity` / <FROM_MODEL_PROFILE>. "
            "If REFERENCE_IMAGE exists: **never** use profile for clothing or accessories — only the reference photo + USER_TEXT. "
            "**Always** use profile for `subject.identity` (face, skin tone, body_type, hair color traits, marks) — **not** from the reference sitter's face or body. "
            "**`hair_in_scene`** follows REFERENCE_IMAGE when HAIRSTYLE_MODE is POSE_REFERENCE; do not force the profile's default hairstyle if it conflicts with REFERENCE_IMAGE.)"
        )
    if model_profile_text and model_profile_text.strip():
        blocks.append(model_profile_text.strip())
    else:
        blocks.append(
            "(no model selected — use neutral, minimal identity only where required, or from USER_TEXT only)"
        )

    mode_extra = _studio_mode_refiner_block(studio_mode)
    if mode_extra:
        blocks.append(mode_extra.strip())

    u = (user_text or "").strip()
    blocks.append("## USER_TEXT (mood, tweaks; does not override reference layout unless clearly contradictory)\n" + (u if u else "(no additional text)"))
    blocks.append(
        aspect_user_block_english(
            output_aspect_key, preserve_reference_framing=has_ref
        )
    )
    return "\n\n".join(blocks)


async def refine_prompt_via_openai(
    *,
    system_instruction: str,
    skeleton: str,
    user_text: str,
    reference_scene_description: str | None,
    model_profile_text: str | None,
    output_aspect_key: str,
    studio_mode: str = "model",
    lock_model_hairstyle: bool = True,
    credentials: StudioOpenAiCredentials | None = None,
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
        studio_mode=studio_mode,
        lock_model_hairstyle=lock_model_hairstyle,
    )
    raw = await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system_instruction.strip()},
            {"role": "user", "content": user_message},
        ],
        max_tokens=8192,
        temperature=0.55,
        credentials=credentials,
    )
    return apply_canonical_realism_to_refined_output(raw)


_DEFAULT_MODEL_PROFILE_GEN_SYSTEM = (
    'Return only JSON: {"model_profile": { ... }} describing identity from photos '
    "(face, hair, skin, body, marks) — not pose, outfit, or scene. English, nested fields."
)


def load_model_profile_gen_system() -> str:
    rel = _relative_prompt_path(
        settings.image_studio_model_profile_gen_system_path,
        "data/prompts/model_profile_from_photos_system.txt",
    )
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file():
        t = path.read_text(encoding="utf-8").strip()
        if t:
            return t
    inline = (settings.image_studio_model_profile_gen_system_inline or "").strip()
    if inline:
        return inline
    log.warning("model_profile_gen: system file missing, using built-in default")
    return _DEFAULT_MODEL_PROFILE_GEN_SYSTEM


def _normalize_model_profile_json_output(raw_text: str) -> str:
    t = _strip_code_fences(raw_text)
    try:
        data = json.loads(t)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Модель вернула не JSON: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError("Ответ должен быть JSON-объектом")
    if "model_profile" not in data:
        data = {"model_profile": data}
    return json.dumps(data, ensure_ascii=False, indent=2)


async def generate_model_profile_json_from_images(
    *, image_items: list[tuple[bytes, str | None]], credentials: StudioOpenAiCredentials | None = None
) -> str:
    """Один vision-запрос: несколько фото одного человека → JSON model_profile."""
    if not image_items:
        raise RuntimeError("Нет изображений")
    system = load_model_profile_gen_system()
    if not system.strip():
        raise RuntimeError("Пустой системный промпт генерации профиля")
    user_content: list[dict] = [
        {
            "type": "text",
            "text": (
                "These reference photos show one person. Output the JSON as instructed. "
                f"Number of images: {len(image_items)}."
            ),
        }
    ]
    for raw, mime in image_items:
        m = (mime or "image/jpeg").split(";")[0].strip()
        if m not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            m = "image/jpeg"
        b64 = base64.standard_b64encode(raw).decode("ascii")
        user_content.append(
            {"type": "image_url", "image_url": {"url": f"data:{m};base64,{b64}"}}
        )
    model = (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model
    raw_text = await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        max_tokens=8192,
        temperature=0.35,
        credentials=credentials,
    )
    return _normalize_model_profile_json_output(raw_text)
