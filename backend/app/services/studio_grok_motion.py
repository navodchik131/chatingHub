"""
Двухшаговый Grok (OpenAI-compatible /v1): описание референс-движения из видео
(полный файл через xAI Files + /v1/responses, либо fallback — сэмплы 1 Hz jpeg),
затем подстановка сохранённой модели под первый кадр целевого ролика.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.studio_motion_video import (
    extract_video_timeline_frames_jpeg,
    probe_video_duration_seconds,
    transcode_motion_video_mp4_under_size,
)
from app.services.studio_openai import StudioOpenAiCredentials, chat_completion_openai_compatible_text

log = logging.getLogger(__name__)

_TIMELINE_SYSTEM_EN = (
    "You follow instructions precisely. Reply only in English as requested. "
    "No preamble, no markdown code fences unless the schema explicitly asks for plain section headers "
    "[t s] lines without ``` blocks."
)

_SEEDANCE_T2V_GROK_SYSTEM_EN = (
    "You follow instructions precisely. "
    "Output ONLY the final Seedance 2.0 video prompt in English. "
    "Keep @ImageN and @VideoN tags exactly as Latin tokens — never translate or localize tag names. "
    "No preamble, no markdown fences."
)

_SEEDANCE_T2V_GROK_SYSTEM_ZH = (
    "You follow instructions precisely. "
    "Output ONLY the final Seedance 2.0 video prompt in Simplified Chinese (简体中文). "
    "Keep @ImageN and @VideoN tags exactly as Latin tokens — never translate or localize tag names. "
    "No preamble, no markdown fences."
)

# Shared guard for step2 + Seedance expand (video APIs flag detailed face/identity prose).
_VIDEO_IDENTITY_GUARD_EN = (
    "CONTENT_SAFETY (video provider): Do NOT write detailed facial identity in prose — "
    "no eye color, lip shape, cheekbones, ethnicity, age, makeup catalog, skin texture, pores, "
    "scars/tattoos on face, or distinctive biometric lists. Identity is locked via reference images "
    "(@Image tags) and the first-frame still; text may only use short neutral face-MOTION tokens "
    "(blink, brow lift, lips part) without describing who the person is."
)

_VIDEO_IDENTITY_GUARD_SOFT_EN = (
    "CONTENT_SAFETY: Keep prose cinematic — describe scene, motion, camera, wardrobe. "
    "Do not catalog facial features in text; bind the lead character via @Image tag numbers only. "
    "Avoid words like swap, replace performer, or never adopt actor face."
)


def _compact_model_profile_for_video_grok(profile: str) -> str:
    """
    Убирает из JSON-профиля каталог лица перед Grok video prompt — идентичность через @Image.
    Не-JSON профиль возвращаем как есть (инструкции Grok всё равно запрещают копировать лицо).
    """
    p = (profile or "").strip()
    if not p:
        return p
    try:
        data = json.loads(p)
    except json.JSONDecodeError:
        return p
    if not isinstance(data, dict):
        return p

    def _trim_identity_block(ident: dict) -> None:
        for key in ("face_features", "ethnicity", "age", "distinctive_marks"):
            ident.pop(key, None)
        skin = ident.get("skin")
        if isinstance(skin, dict):
            skin.pop("tone", None)
            skin.pop("imperfections", None)
            if not skin:
                ident.pop("skin", None)

    subject = data.get("subject")
    if isinstance(subject, dict):
        ident = subject.get("identity")
        if isinstance(ident, dict):
            _trim_identity_block(ident)
        subject.pop("expression", None)
    elif isinstance(data.get("identity"), dict):
        _trim_identity_block(data["identity"])

    compact = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (
        f"{compact}\n"
        "[VIDEO: face/skin identity omitted — use @Image model references; "
        "hair length and body_type only for continuity.]"
    )


def grok_motion_studio_credentials() -> StudioOpenAiCredentials:
    key = (settings.grok_api_key or "").strip() or (settings.openai_api_key or "").strip()
    if not key:
        raise RuntimeError(
            "Задайте GROK_API_KEY в .env (или временно OPENAI_API_KEY) для Grok motion timeline."
        )
    base = (settings.grok_base_url or "").strip().rstrip("/")
    if not base:
        base = (settings.openai_base_url or "").strip().rstrip("/")
    if not base:
        base = "https://api.x.ai/v1"
    return StudioOpenAiCredentials(api_key=key, base_url=base, organization="")


def _grok_fps_stills_model() -> str:
    for raw in (
        settings.grok_motion_model,
        settings.openai_studio_model_vision,
        settings.openai_studio_model,
    ):
        m = (raw or "").strip()
        if m:
            return m
    return "grok-2-vision-1212"


def _grok_full_video_responses_model() -> str:
    m = (settings.grok_motion_full_video_model or "").strip()
    return m if m else "grok-4"


def _api_root_from_v1(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def _base_url_hosts_xai_api(base_url: str) -> bool:
    raw = (base_url or "").strip()
    if not raw:
        return False
    if not raw.startswith("http"):
        raw = "https://" + raw.lstrip("/")
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    return host.endswith(".x.ai") or host == "x.ai"


async def _xai_upload_mp4_for_responses(
    *,
    credentials: StudioOpenAiCredentials,
    mp4_path: Path,
    timeout_seconds: float,
) -> str:
    root = _api_root_from_v1(credentials.base_url)
    url = f"{root}/files"
    headers = {"Authorization": f"Bearer {credentials.api_key.strip()}"}
    data = {"purpose": "assistants"}
    file_bytes = mp4_path.read_bytes()
    fname = mp4_path.name or "motion_ref.mp4"
    files = {"file": (fname, file_bytes, "video/mp4")}
    to = max(120.0, float(timeout_seconds))
    async with httpx.AsyncClient(timeout=to) as client:
        r = await client.post(url, headers=headers, data=data, files=files)

    body = r.text[:2000]
    if r.status_code >= 400:
        raise RuntimeError(f"xAI Files upload HTTP {r.status_code}: {body}")

    try:
        payload = r.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"xAI Files upload invalid JSON: {body}") from e

    fid = ""
    if isinstance(payload, dict):
        fid = str(payload.get("id") or "").strip()
    if not fid:
        raise RuntimeError(f"xAI Files upload: missing file id: {payload!r}")

    log.info("grok motion uploaded video file_id=%s size=%s", fid[:24], len(file_bytes))
    return fid


async def _xai_delete_file_maybe(
    *,
    credentials: StudioOpenAiCredentials,
    file_id: str,
    timeout_seconds: float,
) -> None:
    fid = (file_id or "").strip()
    if not fid:
        return
    root = _api_root_from_v1(credentials.base_url)
    url = f"{root}/files/{fid}"
    headers = {"Authorization": f"Bearer {credentials.api_key.strip()}"}
    try:
        async with httpx.AsyncClient(timeout=min(120.0, float(timeout_seconds))) as client:
            r = await client.delete(url, headers=headers)
        if r.status_code >= 400:
            log.warning("xAI Files delete HTTP %s: %s", r.status_code, (r.text or "")[:500])
    except Exception as e:
        log.warning("xAI Files delete failed: %s", e)


def _extract_output_text_from_xai_responses(payload: dict) -> str:
    """Сбор текста из тела успешного ответа POST /v1/responses."""
    chunks: list[str] = []

    items = payload.get("output")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, str):
                s = content.strip()
                if s:
                    chunks.append(s)
                continue
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, str):
                    s = part.strip()
                    if s:
                        chunks.append(s)
                    continue
                if not isinstance(part, dict):
                    continue
                t = part.get("text")
                if isinstance(t, str):
                    tt = t.strip()
                    if tt:
                        chunks.append(tt)

    if chunks:
        return "\n\n".join(chunks).strip()

    for key in ("error",):
        block = payload.get(key)
        if isinstance(block, dict):
            msg = block.get("message")
            if isinstance(msg, str) and msg.strip():
                raise RuntimeError(f"xAI Responses error payload: {msg.strip()}")

    text = ""
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        ch0 = choices[0]
        if isinstance(ch0, dict):
            msg = ch0.get("message")
            if isinstance(msg, dict):
                c = msg.get("content")
                if isinstance(c, str):
                    text = c.strip()
    if text:
        return text

    raise RuntimeError(f"xAI Responses: unsupported response shape keys={list(payload.keys())[:12]}")


async def _xai_responses_video_timeline_text(
    *,
    credentials: StudioOpenAiCredentials,
    instruction_text: str,
    file_id: str,
    model: str,
    timeout_seconds: float,
    max_completion_tokens: int = 8192,
) -> str:
    root = _api_root_from_v1(credentials.base_url)
    url = f"{root}/responses"
    headers = {
        "Authorization": f"Bearer {credentials.api_key.strip()}",
        "Content-Type": "application/json",
    }
    fid = file_id.strip()
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": instruction_text.strip()},
                    {"type": "input_file", "file_id": fid},
                ],
            }
        ],
        "temperature": 0.25,
    }
    if max_completion_tokens and max_completion_tokens > 0:
        body["max_output_tokens"] = max_completion_tokens

    to = max(180.0, float(timeout_seconds))
    async with httpx.AsyncClient(timeout=to) as client:
        r = await client.post(url, headers=headers, json=body)

    raw_snip = (r.text or "")[:2500]
    if r.status_code >= 400:
        raise RuntimeError(f"xAI Responses HTTP {r.status_code}: {raw_snip}")

    try:
        payload = r.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"xAI Responses invalid JSON: {raw_snip}") from e

    text = _extract_output_text_from_xai_responses(payload)
    text = text.strip()
    if len(text) < 80:
        raise RuntimeError("Grok (video) вернул слишком короткое описание таймлайна.")
    log.info("grok motion full-video chars=%s", len(text))
    return text


def _timeline_instruction_fps_stills_intro(n_frames: int) -> str:
    return (
        f"You are given {n_frames} still images in chronological order. "
        "They are 1 Hz samples from the start of a short reference video — image i ≈ second i from t=0.\n"
        "Write ONE continuous English video-generation brief that can drive image-to-video.\n"
        "Structure:\n"
        "- For each second t from 0 through N-1 (N = number of images), output a line starting with "
        "the exact token `[t s]` then a rich description: full-body pose, limb angles, weight shifts, "
        "head angle and gaze direction, hair motion, clothing folds, hands, micro-movements, "
        "camera position/move (pan/tilt/dolly/track), lens feel, background parallax, lighting direction and quality.\n"
        "- Face/choreography per second: at most a few neutral MOTION tokens (e.g. \"brows lift\", \"lips press then part\", "
        "\"eyes narrow slightly\") — timings only; NEVER face shape, beauty, ethnicity, age, makeup, skin, or eye color.\n"
        "- Then one paragraph prefixed `[Global motion]` summarizing rhythm, energy, transitions between seconds, "
        "and any repeating beats.\n"
        "Rules: describe only what is visible; do not invent story beats; do not name real celebrities; "
        "performer wording = body silhouette + wardrobe + props only (identity will be swapped later); "
        "preserve motion and timing faithfully; no facial identity catalog.\n"
        "Plain text only (no Markdown tables)."
    )


def _timeline_instruction_full_video_intro(*, capped_seconds: int, approximate_duration: float | None) -> str:
    dur_note = ""
    if approximate_duration is not None and approximate_duration > 0:
        dur_note = (
            f"Approximate full source duration ~{approximate_duration:.1f}s — you see only the clipped segment "
            "that follows.\n\n"
        )
    last_second = max(0, capped_seconds - 1)
    return (
        "The ATTACHED VIDEO FILE is your only temporal reference.\n"
        "Watch continuous motion — not inferred from sparse stills.\n"
        f"The clip analyzed is capped at roughly the first **{capped_seconds} seconds**.\n\n"
        f"{dur_note}"
        "Write ONE continuous English brief for image-to-video / motion-transfer.\n"
        "Structure (plain text):\n"
        f"- For each integer second t from **0** through **{last_second}** (one `[t s]` line per second that you can "
        "confidently sample from playback), emit one line beginning with **`[t s]`** describing for that beat: "
        "full-body pose, torso twist and weight shifts, articulate arms/hands/fingers where visible, gait or step cues, "
        "head yaw/tilt and gaze versus camera lens, optional brief face-MOTION cues (blink, brow/lip/jaw timing only — "
        "no face shape, skin, eye color, ethnicity, makeup, or beauty descriptors), "
        "hair inertia, garment folds reacting to motion.\n"
        "- Camera: pan/tilt/dolly/track, stabilization feel, handheld micro-shake vs tripod, framing shifts, focal length cues, background parallax.\n"
        "- Lighting: dominant key/fill directions and how highlights travel with moving surfaces.\n"
        "- Dialogue / lip flap: IF speech or lip syncing is visibly present, annotate **sub-word level** pacing (do NOT transcribe full dialogue unless audible & clear); otherwise omit.\n"
        "- Closing paragraph **`[Global motion]`**: overall rhythm, energy arc, entrances/exits from frame, repeated gestures, climax micro-beats.\n"
        "Rules:\n"
        "- Describe ONLY what occurs in-video; avoid invented plot beats.\n"
        "- Neutral performer wording: motion, wardrobe, body silhouette — not a facial identity write-up.\n"
        "- No markdown tables; no fenced code blocks.\n"
    )


async def grok_step1_timeline_from_fps_jpegs(
    *,
    frames: list[bytes],
    credentials: StudioOpenAiCredentials,
) -> str:
    if not frames:
        raise RuntimeError("Нет jpeg-кадров для Grok (ffmpeg).")

    model = _grok_fps_stills_model()
    intro = _timeline_instruction_fps_stills_intro(len(frames))

    content: list[dict] = [{"type": "text", "text": intro}]
    for i, raw in enumerate(frames):
        b64 = base64.standard_b64encode(raw).decode("ascii")
        content.append({"type": "text", "text": f"Sample at ~{i} s:"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            },
        )

    out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": _TIMELINE_SYSTEM_EN},
            {"role": "user", "content": content},
        ],
        max_tokens=8192,
        temperature=0.25,
        credentials=credentials,
        timeout_seconds=float(settings.studio_archive_download_timeout_seconds),
    )
    text = (out or "").strip()
    if len(text) < 80:
        raise RuntimeError("Grok вернул слишком короткое описание таймлайна.")
    log.info("grok motion step1 (fps jpeg) chars=%s frames=%s", len(text), len(frames))
    return text


async def grok_step1_timeline_from_video_native_mp4(
    *,
    video_path: Path,
    credentials: StudioOpenAiCredentials,
) -> str:
    cap = settings.grok_motion_max_seconds
    tmp_mp4: Path | None = None
    file_id_remote: str | None = None
    try:
        tmp_mp4 = transcode_motion_video_mp4_under_size(
            video_path,
            max_duration_sec=cap,
            target_max_bytes=int(settings.grok_motion_xai_upload_max_bytes),
        )
        file_id_remote = await _xai_upload_mp4_for_responses(
            credentials=credentials,
            mp4_path=tmp_mp4,
            timeout_seconds=settings.studio_archive_download_timeout_seconds + 120.0,
        )
        approx_dur = probe_video_duration_seconds(video_path)
        intro = _timeline_instruction_full_video_intro(
            capped_seconds=max(1, min(120, int(cap))),
            approximate_duration=float(approx_dur) if approx_dur else None,
        )
        model = _grok_full_video_responses_model()

        text = await _xai_responses_video_timeline_text(
            credentials=credentials,
            instruction_text=intro,
            file_id=file_id_remote,
            model=model,
            timeout_seconds=settings.grok_motion_full_video_timeout_seconds,
            max_completion_tokens=8192,
        )
        return text
    finally:
        if tmp_mp4 is not None:
            tmp_mp4.unlink(missing_ok=True)
        if file_id_remote:
            await _xai_delete_file_maybe(
                credentials=credentials,
                file_id=file_id_remote,
                timeout_seconds=min(120.0, settings.studio_archive_download_timeout_seconds),
            )


async def grok_step1_timeline_from_video(
    *,
    video_path: Path,
    credentials: StudioOpenAiCredentials,
) -> str:
    use_native = settings.grok_motion_send_full_video and _base_url_hosts_xai_api(
        credentials.base_url
    )
    if use_native:
        try:
            return await grok_step1_timeline_from_video_native_mp4(
                video_path=video_path, credentials=credentials
            )
        except Exception as e:
            log.warning("grok motion full-video timeline failed (%s); fallback=%s", e, settings.grok_motion_native_video_fallback_frames)
            if not settings.grok_motion_native_video_fallback_frames:
                raise

    frames, _span = extract_video_timeline_frames_jpeg(
        video_path,
        max_seconds=settings.grok_motion_max_seconds,
        max_width=settings.grok_motion_max_frame_width,
    )
    return await grok_step1_timeline_from_fps_jpegs(frames=frames, credentials=credentials)


async def grok_step2_rewrite_for_target_model(
    *,
    timeline_english: str,
    model_profile_text: str,
    first_frame_jpeg: bytes,
    first_frame_media: str,
    credentials: StudioOpenAiCredentials,
) -> str:
    model = _grok_fps_stills_model()
    mime = (first_frame_media or "image/jpeg").split(";")[0].strip()
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"
    b64 = base64.standard_b64encode(first_frame_jpeg).decode("ascii")

    profile = _compact_model_profile_for_video_grok((model_profile_text or "").strip())
    profile_block = (
        profile
        if profile
        else "TARGET_MODEL_PROFILE (text): empty — derive target persona only from the attached first-frame image;"
        " assume it is the canonical look for the synthesized video."
    )

    user_instruction = (
        "You merge a motion timeline with a locked target persona for video generation.\n\n"
        f"{_VIDEO_IDENTITY_GUARD_EN}\n\n"
        f"{profile_block}\n\n"
        "TARGET_MODEL_PROFILE usage: context for wardrobe/hair length continuity only — "
        "do NOT paste face_features, ethnicity, skin, eye color, or distinctive_marks into the output text.\n\n"
        "---\n"
        "REFERENCE_MOTION_TIMELINE (English, keep choreography and timing exactly):\n"
        f"{timeline_english.strip()}\n\n"
        "---\n"
        "TASK:\n"
        "1) Read REFERENCE_MOTION_TIMELINE. Preserve every `[t s]` line and `[Global motion]` pacing — "
        "do not shorten the seconds coverage; keep the same chronological structure.\n"
        "2) Remove or shorten any identity/appearance catalog in the timeline (face shape, ethnicity, makeup, "
        "skin texture, eye color, age, beauty adjectives, detailed micro-anatomy). Identity is implicit from "
        "the attached first-frame image + downstream @Image reference tags — never restate it in prose.\n"
        "3) Per `[t s]` line keep: full-body pose, limbs, weight, gait, torso, hands, head yaw/pitch/tilt, "
        "gaze direction, hair movement, clothing folds, camera, lighting, environment. "
        "Face: only short neutral MOTION tokens from the timeline (max ~12 words of face wording per second); "
        "preserve timing, not biometric detail.\n"
        "4) Do NOT invent new motions, camera beats, backgrounds, props, lighting setup, or durations.\n"
        "5) If the profile implies hair length or wardrobe and the timeline is silent, add at most one short "
        "continuity phrase in `[Global motion]` without changing poses.\n"
        "Output: a single plain English brief (same `[t s]` + `[Global motion]` skeleton), ready to paste "
        "into an image-to-video model together with the first-frame image.\n"
    )

    content: list[dict] = [
        {"type": "text", "text": user_instruction},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        },
    ]

    out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": _TIMELINE_SYSTEM_EN},
            {"role": "user", "content": content},
        ],
        max_tokens=10240,
        temperature=0.2,
        credentials=credentials,
        timeout_seconds=min(600.0, float(settings.studio_archive_download_timeout_seconds) + 180.0),
    )
    text = (out or "").strip()
    if len(text) < 80:
        raise RuntimeError("Grok вернул слишком короткий итоговый промпт.")
    log.info("grok motion step2 chars=%s", len(text))
    return text


async def grok_two_step_motion_prompt_for_studio(
    *,
    video_path: Path,
    model_profile_text: str,
    first_frame_jpeg: bytes,
    first_frame_media: str,
    credentials: StudioOpenAiCredentials,
) -> str:
    timeline = await grok_step1_timeline_from_video(video_path=video_path, credentials=credentials)
    return await grok_step2_rewrite_for_target_model(
        timeline_english=timeline,
        model_profile_text=model_profile_text,
        first_frame_jpeg=first_frame_jpeg,
        first_frame_media=first_frame_media,
        credentials=credentials,
    )


def grok_motion_api_configured() -> bool:
    return bool((settings.grok_api_key or "").strip() or (settings.openai_api_key or "").strip())


_WORKFLOW_VIDEO_PROMPT_SYSTEM = (
    "You write complete video-generation prompts for AI image-to-video models (Seedance, Grok Imagine Video). "
    "Output ONLY the final prompt in English as plain text. "
    "Describe what happens second-by-second: body motion, gestures, gaze, camera, lighting, environment. "
    "Preserve the chronological structure and timing from MOTION_TIMELINE — do not invent new beats. "
    "Use REFERENCE_CONTEXT for character identity, wardrobe, and scene continuity — do not paste long "
    "biometric catalogs; keep face identity implicit via references. "
    "No markdown, no bullet lists, no @Image/@Video tags, no labels like Prompt:."
)


async def grok_compose_workflow_video_prompt(
    *,
    motion_timeline: str,
    model_profile_text: str,
    first_frame_jpeg: bytes,
    first_frame_media: str,
    first_frame_scene: str | None,
    reference_blocks: list[str],
    user_notes: str,
    credentials: StudioOpenAiCredentials | None = None,
    max_chars: int = 6000,
) -> str:
    """Собирает финальный промпт для video gen из timeline + still-контекста."""
    import base64

    creds = credentials or grok_motion_studio_credentials()
    model = _grok_fps_stills_model()
    mime = (first_frame_media or "image/jpeg").split(";")[0].strip()
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"
    b64 = base64.standard_b64encode(first_frame_jpeg).decode("ascii")

    profile = _compact_model_profile_for_video_grok((model_profile_text or "").strip())
    sections: list[str] = []
    if profile:
        sections.append(f"MODEL_PROFILE (context only, do not paste verbatim):\n{profile}")
    sections.append(
        "MOTION_TIMELINE (preserve choreography and `[t s]` timing exactly):\n"
        + (motion_timeline or "").strip()
    )
    if first_frame_scene:
        sections.append(f"OPENING_FRAME_SCENE:\n{first_frame_scene.strip()}")
    if reference_blocks:
        sections.append(
            "REFERENCE_CONTEXT:\n" + "\n\n".join(reference_blocks)
        )
    if (user_notes or "").strip():
        sections.append(f"USER_DIRECTION:\n{user_notes.strip()}")

    user_instruction = (
        "Synthesize one cinematic video-generation prompt from the inputs below.\n"
        "Keep the motion timeline structure; merge reference identity and scene details.\n\n"
        + "\n\n---\n\n".join(sections)
    )

    content: list[dict] = [
        {"type": "text", "text": user_instruction},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        },
    ]

    out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": _WORKFLOW_VIDEO_PROMPT_SYSTEM},
            {"role": "user", "content": content},
        ],
        max_tokens=10240,
        temperature=0.25,
        credentials=creds,
        timeout_seconds=min(600.0, float(settings.studio_archive_download_timeout_seconds) + 180.0),
    )
    text = (out or "").strip()
    if len(text) < 40:
        raise RuntimeError("Grok вернул слишком короткий промпт.")
    return text[:max_chars]


_GROK_IMAGINE_I2V_SYSTEM = (
    "You write image-to-video prompts for xAI Grok Imagine Video v1.5. "
    "Output ONLY the final prompt in English as plain text. "
    "Describe subject motion, camera movement, lighting changes, and atmosphere. "
    "Do not repeat static details already visible in the start frame. "
    "No markdown, no bullet lists, no @Image tags, no labels like Prompt:."
)


async def build_grok_imagine_i2v_prompt(
    *,
    user_brief: str,
    duration_seconds: int = 6,
    credentials: StudioOpenAiCredentials | None = None,
    max_chars: int = 2000,
) -> tuple[str, str]:
    """Grok (если настроен) → иначе user brief. Возвращает (prompt, source: grok|template)."""
    brief = (user_brief or "").strip()
    if not brief:
        brief = (
            "Natural subtle motion aligned with the scene, cinematic camera, "
            "stable identity, smooth movement, realistic lighting."
        )
    if grok_motion_api_configured():
        try:
            creds = credentials or grok_motion_studio_credentials()
            model = _grok_fps_stills_model()
            dur = max(1, min(15, int(duration_seconds)))
            user_msg = f"Duration: {dur} seconds.\nUser request:\n{brief}"
            out = await chat_completion_openai_compatible_text(
                model=model,
                messages=[
                    {"role": "system", "content": _GROK_IMAGINE_I2V_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=2048,
                temperature=0.35,
                credentials=creds,
            )
            p = (out or "").strip()
            if len(p) >= 20:
                return (p[:max_chars], "grok")
        except Exception as e:
            log.warning("grok imagine i2v prompt failed, template fallback: %s", e)
    return (brief[:max_chars], "template")


def _seedance_image_tag_range(
    n_model: int,
    n_outfit: int,
    *,
    n_start_frame: int = 0,
    soft: bool = False,
) -> str:
    parts: list[str] = []
    if n_start_frame > 0:
        if soft:
            parts.append(
                "@Image1 = opening still at t=0 (pose, wardrobe, lighting, framing — scene reference)"
            )
        else:
            parts.append(
                "@Image1 = approved opening still at t=0 (pose, wardrobe, lighting, framing, environment — "
                "NOT the primary face/body identity source)"
            )
    if n_model > 0:
        start_idx = 1 + n_start_frame
        end_idx = start_idx + n_model - 1
        if soft:
            if n_model == 1:
                parts.append(
                    f"@Image{start_idx} = character-sheet reference for the lead character look"
                )
            else:
                parts.append(
                    f"@Image{start_idx}–@Image{end_idx} = character-sheet references for the lead character look"
                )
        elif n_model == 1:
            parts.append(
                f"@Image{start_idx} = character identity via reference sheet(s) — bind face/body/hair in the API; "
                "do not catalog facial identity in prompt prose"
            )
        else:
            parts.append(
                f"@Image{start_idx}–@Image{end_idx} = same character identity across model reference sheet(s); "
                "bind face/body/hair via tags — never describe the @Video1 actor's face in text"
            )
    if n_outfit > 0:
        idx = 1 + n_start_frame + n_model
        parts.append(f"@Image{idx} = outfit / garment reference (match clothing when describing wardrobe)")
    return "; ".join(parts)


async def grok_expand_seedance_t2v_prompt(
    *,
    user_brief: str,
    n_start_frame: int = 0,
    n_model_images: int,
    n_outfit_images: int = 0,
    n_motion_videos: int = 0,
    motion_notes: str | None = None,
    model_profile_text: str | None = None,
    negative: str | None = None,
    output_aspect: str | None = None,
    duration_seconds: int = 5,
    max_chars: int | None = None,
    credentials: StudioOpenAiCredentials | None = None,
    soft_identity: bool = False,
) -> str:
    """
    Разворачивает краткий запрос пользователя в кинематографический промпт Seedance T2V
    с @ImageN / @VideoN. Обрезает до max_chars.
    """
    from app.services.studio_seedance_t2v import truncate_seedance_t2v_prompt

    brief = (user_brief or "").strip()
    if not brief:
        raise RuntimeError("Пустой запрос для Grok.")

    creds = credentials or grok_motion_studio_credentials()
    model = _grok_fps_stills_model()
    lim = max_chars if max_chars is not None else settings.studio_seedance_t2v_prompt_max_chars

    ref_lines: list[str] = []
    if n_start_frame > 0 or n_model_images > 0 or n_outfit_images > 0:
        ref_lines.append(
            _seedance_image_tag_range(
                n_model_images,
                n_outfit_images,
                n_start_frame=n_start_frame,
                soft=soft_identity,
            )
        )
    if n_motion_videos > 0:
        id_tags = ""
        if n_model_images > 0:
            start_idx = 1 + n_start_frame
            end_idx = start_idx + n_model_images - 1
            id_tags = (
                f"@Image{start_idx}"
                if n_model_images == 1
                else f"@Image{start_idx}–@Image{end_idx}"
            )
        if soft_identity:
            ref_lines.append(
                "@Video1 = motion / pacing / gestures reference"
                + (f"; on-screen character matches {id_tags}" if id_tags else "")
            )
        else:
            ref_lines.append(
                "@Video1 = motion / pacing / body dynamics ONLY (timing, gestures, camera — "
                "NEVER copy the reference video performer's face or body)"
                + (f"; appearance stays from {id_tags}" if id_tags else "")
            )
    ref_block = "\n".join(ref_lines) if ref_lines else "No reference tags (text-only scene)."

    profile = _compact_model_profile_for_video_grok((model_profile_text or "").strip())
    profile_block = profile if profile else "(empty — derive persona only from @Image references)"

    notes = (motion_notes or "").strip()
    notes_block = notes if notes else "(none)"

    neg = (negative or "").strip()
    neg_line = f"Avoid: {neg}" if neg else "(none specified)"

    aspect = (output_aspect or "16:9").strip() or "16:9"
    from app.services.studio_motion_pricing import motion_video_duration_seconds

    dur = motion_video_duration_seconds(duration_seconds)

    output_lang = (
        "Simplified Chinese (简体中文)"
        if settings.studio_seedance_grok_prompt_zh
        else "English"
    )
    guard = _VIDEO_IDENTITY_GUARD_SOFT_EN if soft_identity else _VIDEO_IDENTITY_GUARD_EN
    user_instruction = (
        f"You write a single Seedance 2.0 Text-to-Video prompt in {output_lang}.\n\n"
        f"{guard}\n\n"
        f"USER_BRIEF (any language — interpret intent):\n{brief}\n\n"
        f"REFERENCE_TAG_RULES (order matches API reference_images / reference_videos arrays):\n{ref_block}\n\n"
        f"TARGET_MODEL_PROFILE (context only — do not copy face_features into output):\n{profile_block}\n\n"
        f"MOTION_NOTES_FROM_REFERENCE_VIDEO (optional — distill to motion/camera; strip identity prose):\n{notes_block}\n\n"
        f"NEGATIVE:\n{neg_line}\n\n"
        f"OUTPUT_SPECS: aspect_ratio {aspect}, duration {dur} seconds, cinematic, native audio.\n\n"
        "RULES:\n"
        "1) Output ONLY the final video prompt text — no preamble, no markdown fences.\n"
        f"2) Hard limit: entire output MUST be at most {lim} characters.\n"
    )
    if soft_identity:
        user_instruction += (
            "3) Mention @Image tag numbers once or twice in natural cinematic prose — "
            "do not repeat aggressive identity-lock paragraphs.\n"
            "4) @Video1 supplies timing and body movement; the lead character look comes from the character-sheet @Image tag.\n"
            "5) Wardrobe at t=0 follows @Image1 and USER_BRIEF.\n"
            "6) Include camera, lighting, mood, environment, wardrobe, and choreography with director-level detail.\n"
            "7) Do not invent extra @Image or @Video tags beyond the ranges given.\n"
            "8) No facial feature catalogs, no swap/replace-performer wording.\n"
        )
    else:
        user_instruction += (
            "3) Use @Image tags exactly as assigned: @Image1 = opening still only; "
            "face/body/hair identity ONLY from the model @Image tag range — repeat those @Image numbers "
            "at least twice in the prompt (never vague \"model references\" without @Image numbers).\n"
            "4) @Video1 is attached for motion/choreography ONLY — follow its timing and gestures but "
            "NEVER adopt the reference video performer's face, body, hair, or skin; identity stays on model @Image tags "
            "for the ENTIRE clip including after 2–3 seconds.\n"
            "5) Wardrobe at t=0 comes from @Image1 and USER_BRIEF.\n"
            "6) Include camera, lighting, mood, environment, wardrobe, and body choreography with director-level detail; "
            "keep one continuous scene for the clip duration.\n"
            "7) Do not invent extra @Image or @Video tags beyond the ranges given.\n"
            "8) Never output detailed facial identity lists in prose — bind identity only via explicit @Image tag numbers.\n"
            "9) If USER_BRIEF or MOTION_NOTES contain `[t s]` timelines, keep timing but compress any face lines to motion-only tokens.\n"
        )
    if settings.studio_seedance_grok_prompt_zh:
        user_instruction += (
            "10) Write the entire prompt body in Simplified Chinese. "
            "Keep @ImageN / @VideoN tags in Latin as-is.\n"
        )
    else:
        user_instruction += (
            "10) Write the entire prompt body in English. "
            "Keep @ImageN / @VideoN tags in Latin as-is.\n"
        )

    system_content = (
        _SEEDANCE_T2V_GROK_SYSTEM_ZH
        if settings.studio_seedance_grok_prompt_zh
        else _SEEDANCE_T2V_GROK_SYSTEM_EN
    )

    out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_instruction},
        ],
        max_tokens=4096,
        temperature=0.35,
        credentials=creds,
        timeout_seconds=min(600.0, float(settings.studio_archive_download_timeout_seconds) + 120.0),
    )
    text = truncate_seedance_t2v_prompt((out or "").strip(), max_chars=lim)
    if len(text) < 40:
        raise RuntimeError("Grok вернул слишком короткий промпт для Seedance T2V.")
    log.info("grok seedance t2v prompt chars=%s", len(text))
    return text
