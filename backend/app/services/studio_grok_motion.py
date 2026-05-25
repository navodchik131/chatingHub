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
        "head angle and gaze, facial expression micro-changes (brow/jaw/lips timing), hair motion, "
        "clothing folds, hands, micro-movements, camera position/move (pan/tilt/dolly/track), lens feel, "
        "background parallax, lighting direction and quality.\n"
        "- Then one paragraph prefixed `[Global motion]` summarizing rhythm, energy, transitions between seconds, "
        "and any repeating beats.\n"
        "Rules: describe only what is visible; do not invent story beats; do not name real celebrities; "
        "write the performer neutrally (body type, wardrobe, markings) knowing identity will be replaced later — "
        "but preserve motion and timing faithfully.\n"
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
        "head yaw/tilt and gaze versus camera lens, facial micro-movement (**brows, lids, cheeks, lips, jaw** — timings and magnitudes neutrally, no identity guesses), "
        "hair inertia, garment folds reacting to motion.\n"
        "- Camera: pan/tilt/dolly/track, stabilization feel, handheld micro-shake vs tripod, framing shifts, focal length cues, background parallax.\n"
        "- Lighting: dominant key/fill directions and how highlights travel with moving surfaces.\n"
        "- Dialogue / lip flap: IF speech or lip syncing is visibly present, annotate **sub-word level** pacing (do NOT transcribe full dialogue unless audible & clear); otherwise omit.\n"
        "- Closing paragraph **`[Global motion]`**: overall rhythm, energy arc, entrances/exits from frame, repeated gestures, climax micro-beats.\n"
        "Rules:\n"
        "- Describe ONLY what occurs in-video; avoid invented plot beats.\n"
        "- Neutral performer wording (appearance will later be swapped for MODEL_PROFILE).\n"
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

    profile = (model_profile_text or "").strip()
    profile_block = (
        profile
        if profile
        else "TARGET_MODEL_PROFILE (text): empty — derive target persona only from the attached first-frame image;"
        " assume it is the canonical look for the synthesized video."
    )

    user_instruction = (
        "You merge a motion timeline with a locked target persona for video generation.\n\n"
        f"{profile_block}\n\n"
        "---\n"
        "REFERENCE_MOTION_TIMELINE (English, keep choreography and timing exactly):\n"
        f"{timeline_english.strip()}\n\n"
        "---\n"
        "TASK:\n"
        "1) Read REFERENCE_MOTION_TIMELINE. Preserve every `[t s]` line and `[Global motion]` pacing — "
        "do not shorten the seconds coverage; keep the same chronological structure.\n"
        "2) Wherever the timeline describes the on-screen person's identity or appearance "
        "(face shape, ethnicity guess, hair, makeup, physique, tattoos, scars, approximate age/gender cues, wardrobe brand logos), "
        "replace those phrases so they describe ONLY the TARGET_MODEL_PROFILE (text) "
        "+ what is visibly consistent with the attached first-frame image.\n"
        "3) Do NOT rename or invent new motions, camera beats, backgrounds, props, lighting setup, "
        "or durations — choreography and environment stay from the timeline.\n"
        "4) If the timeline is silent about a detail the profile requires (e.g. hair length), harmonize subtly "
        "without changing the poses.\n"
        "5) Maintain detailed facial-micro-expression timing from the timeline; only swap wording to match the locked persona visually.\n"
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


def _seedance_image_tag_range(
    n_model: int,
    n_outfit: int,
    *,
    n_start_frame: int = 0,
) -> str:
    parts: list[str] = []
    if n_start_frame > 0:
        parts.append(
            "@Image1 = approved opening still at t=0 (pose, wardrobe, lighting, framing, environment — "
            "NOT the primary face/body identity source)"
        )
    if n_model > 0:
        start_idx = 1 + n_start_frame
        end_idx = start_idx + n_model - 1
        if n_model == 1:
            parts.append(
                f"@Image{start_idx} = character identity (face, body, hair from model reference sheet(s))"
            )
        else:
            parts.append(
                f"@Image{start_idx}–@Image{end_idx} = same character identity across model reference sheet(s); "
                "use these tags for face, body, hair — never the original actor from @Video1"
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
) -> str:
    """
    Разворачивает краткий запрос пользователя в кинематографический промпт Seedance T2V
    с @ImageN / @VideoN (English). Обрезает до max_chars.
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
            )
        )
    if n_motion_videos > 0:
        ref_lines.append("@Video1 = motion / pacing / body dynamics reference (follow timing and gestures)")
    ref_block = "\n".join(ref_lines) if ref_lines else "No reference tags (text-only scene)."

    profile = (model_profile_text or "").strip()
    profile_block = profile if profile else "(empty — derive persona only from @Image references)"

    notes = (motion_notes or "").strip()
    notes_block = notes if notes else "(none)"

    neg = (negative or "").strip()
    neg_line = f"Avoid: {neg}" if neg else "(none specified)"

    aspect = (output_aspect or "16:9").strip() or "16:9"
    dur = max(4, min(15, int(duration_seconds)))

    user_instruction = (
        "You write a single Seedance 2.0 Text-to-Video prompt in ENGLISH.\n\n"
        f"USER_BRIEF (any language — interpret intent):\n{brief}\n\n"
        f"REFERENCE_TAG_RULES (order matches API reference_images / reference_videos arrays):\n{ref_block}\n\n"
        f"TARGET_MODEL_PROFILE:\n{profile_block}\n\n"
        f"MOTION_NOTES_FROM_REFERENCE_VIDEO (optional):\n{notes_block}\n\n"
        f"NEGATIVE:\n{neg_line}\n\n"
        f"OUTPUT_SPECS: aspect_ratio {aspect}, duration {dur} seconds, cinematic, native audio.\n\n"
        "RULES:\n"
        "1) Output ONLY the final video prompt text — no preamble, no markdown fences.\n"
        f"2) Hard limit: entire output MUST be at most {lim} characters.\n"
        "3) Use @Image tags exactly as assigned above: @Image1 for opening still only; "
        "identity tags for face/body/hair; outfit tag for wardrobe if present.\n"
        "4) If @Video1 exists, reference it for motion/choreography; do not describe the reference video's original actor identity.\n"
        "5) Wardrobe at t=0 comes from @Image1 and USER_BRIEF; identity from model reference @Image tags.\n"
        "6) Include camera, lighting, mood, and action with director-level detail; keep one continuous scene for the clip duration.\n"
        "7) Do not invent extra @Image or @Video tags beyond the ranges given.\n"
    )

    out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": _TIMELINE_SYSTEM_EN},
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
