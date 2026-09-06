"""Grok shot-analyst для Motion Control: video + turnaround → Seedance T2V prompt."""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path

from app.config import BACKEND_DIR
from app.services.studio_grok_motion import (
    _api_root_from_v1,
    _extract_output_text_from_xai_responses,
    _xai_delete_file_maybe,
    _xai_upload_mp4_for_responses,
    grok_motion_studio_credentials,
)
from app.services.studio_openai import StudioOpenAiCredentials, _strip_code_fences
from app.services.studio_motion_video import probe_video_duration_seconds, transcode_motion_video_mp4_under_size
from app.config import settings

log = logging.getLogger(__name__)

_SHOT_ANALYST_NAME = "motion_control_shot_analyst.txt"
_TURNAROUND_SHEET_NAME = "motion_control_turnaround_sheet.txt"


def _motion_control_prompt_candidates(filename: str) -> list[Path]:
    """data/prompts (Docker volume) → _bundled_prompts (образ) — как у Grok compose."""
    ordered = [
        (BACKEND_DIR / "data" / "prompts" / filename).resolve(),
        (BACKEND_DIR / "_bundled_prompts" / filename).resolve(),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for path in ordered:
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _read_first_nonempty_prompt_file(candidates: list[Path]) -> str | None:
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return None


def load_motion_control_turnaround_prompt() -> str:
    text = _read_first_nonempty_prompt_file(_motion_control_prompt_candidates(_TURNAROUND_SHEET_NAME))
    if text:
        return text
    tried = ", ".join(str(p) for p in _motion_control_prompt_candidates(_TURNAROUND_SHEET_NAME))
    raise RuntimeError(f"Промпт развёртки Motion Control не найден (пробовали: {tried})")


def load_motion_control_shot_analyst_prompt() -> str:
    text = _read_first_nonempty_prompt_file(_motion_control_prompt_candidates(_SHOT_ANALYST_NAME))
    if text:
        return text
    tried = ", ".join(str(p) for p in _motion_control_prompt_candidates(_SHOT_ANALYST_NAME))
    raise RuntimeError(f"Промпт Grok shot-analyst не найден (пробовали: {tried})")


def extract_shot_analyst_prompt_block(text: str) -> str:
    """Достаёт промпт из ``` code block или возвращает текст как есть."""
    raw = (text or "").strip()
    if not raw:
        raise RuntimeError("Grok вернул пустой ответ.")
    fenced = _strip_code_fences(raw)
    if fenced and fenced != raw:
        return fenced.strip()
    m = re.search(r"```(?:\w*\n)?(.*?)```", raw, flags=re.DOTALL)
    if m:
        return m.group(1).strip()
    if raw.lower().startswith("cannot be converted") or "cannot be converted" in raw[:200].lower():
        raise RuntimeError(raw.splitlines()[0][:500])
    return raw


def bind_motion_control_seedance_tags(prompt: str, *, has_first_frame: bool = False) -> str:
    """Подставляем @Video1/@ImageN вместо плейсхолдеров Grok."""
    out = (prompt or "").strip()
    out = out.replace("<<<DEPTH_MAP>>>", "@Video1")
    if has_first_frame:
        out = out.replace("<<<FIRST_FRAME_IMAGE>>>", "@Image1")
        out = out.replace("<<<CHARACTER_IMAGE>>>", "@Image2")
    else:
        out = out.replace("<<<CHARACTER_IMAGE>>>", "@Image1")
        out = out.replace("<<<FIRST_FRAME_IMAGE>>>", "")
    return out


_FIRST_FRAME_GROK_APPENDIX = """
---

## ATTACHED THIS RUN: FIRST FRAME IMAGE (second still after CHARACTER IMAGE)

A **FIRST FRAME IMAGE** is attached after the CHARACTER IMAGE. It is the **opening frame at t=0**
of the target video: the character already placed in the scene — environment, lighting, camera
framing, pose, distance, and wardrobe **in context**.

Use it for:
- [GLOBAL SETUP] environment, surfaces, light direction, time of day, and opening pose at t=0
- Shot 1 opening sub-beats: match this frame at t=0 before motion from the depth map takes over

In [SOURCE MATERIAL] you MUST write:
- <<<FIRST_FRAME_IMAGE>>>: opening frame at t=0 — environment, pose, framing, light in scene.
  Protagonist ONLY for placement context; deny turnaround layout artefacts.
- <<<CHARACTER_IMAGE>>>: identity turnaround — face, hair, outfit. Protagonist ONLY.

Generation asset order: @Image1 = opening first frame, @Image2 = character identity,
@Video1 = depth map motion control.

At t=0 the output must match <<<FIRST_FRAME_IMAGE>>> for scene and pose; identity from
<<<CHARACTER_IMAGE>>> for all frames. Motion timing still follows <<<DEPTH_MAP>>> exactly.
"""


def motion_control_grok_audio_policy(
    *,
    wants_reference_audio: bool,
    has_ref_audio: bool,
) -> str:
    """
    PLATE — ref-аудио поверх (Seedance @Audio1 или post-mux): MOUTH TIMING, без AI-звука.
    GENERATE — нет дорожки реф-видео, провайдер синтезирует звук.
    """
    if has_ref_audio:
        return "PLATE"
    if wants_reference_audio:
        return "GENERATE"
    return "PLATE"


_BRIEF_HEADER_TO_KEY: dict[str, str] = {
    "what happens": "what_happens",
    "must transfer": "must_transfer",
    "call it what it is": "call_it",
    "known facts": "known_facts",
    "leave out": "leave_out",
}

_BRIEF_KEY_TO_PLACEHOLDER: dict[str, str] = {
    "what_happens": "<<<BRIEF_WHAT_HAPPENS>>>",
    "must_transfer": "<<<BRIEF_MUST_TRANSFER>>>",
    "call_it": "<<<BRIEF_CALL_IT>>>",
    "known_facts": "<<<BRIEF_KNOWN_FACTS>>>",
    "leave_out": "<<<BRIEF_LEAVE_OUT>>>",
}


def parse_motion_control_user_brief(raw: str) -> dict[str, str]:
    """
    Разбирает текст USER BRIEF из wizard.
    Без заголовков весь текст идёт в WHAT HAPPENS; с заголовками — по секциям 0b.
    """
    text = (raw or "").strip()
    buckets: dict[str, list[str]] = {key: [] for key in _BRIEF_KEY_TO_PLACEHOLDER}
    if not text:
        return {key: "" for key in _BRIEF_KEY_TO_PLACEHOLDER}

    current: str | None = None
    saw_header = False
    for line in text.splitlines():
        stripped = line.strip()
        matched_header = False
        for label, key in _BRIEF_HEADER_TO_KEY.items():
            low = stripped.lower()
            prefix = f"{label}:"
            if low == prefix or low.startswith(prefix):
                current = key
                saw_header = True
                matched_header = True
                rest = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
                if rest:
                    buckets[key].append(rest)
                break
        if matched_header:
            continue
        if current:
            buckets[current].append(line.rstrip())
        elif stripped:
            buckets["what_happens"].append(line.rstrip())

    if saw_header:
        return {key: "\n".join(buckets[key]).strip() for key in _BRIEF_KEY_TO_PLACEHOLDER}
    return {
        key: ("\n".join(buckets[key]).strip() if key == "what_happens" else "")
        for key in _BRIEF_KEY_TO_PLACEHOLDER
    }


def apply_motion_control_shot_analyst_instruction(
    template: str,
    *,
    audio_policy: str,
    user_brief: str = "",
    per_project_notes: str = "",
    has_first_frame: bool = False,
) -> str:
    """Собирает финальную инструкцию: AUDIO POLICY + поля USER BRIEF (секция 0b)."""
    policy = (audio_policy or "PLATE").strip().upper()
    if policy not in ("GENERATE", "PLATE", "HYBRID"):
        policy = "PLATE"
    instruction = (template or "").replace("<<<AUDIO_POLICY>>>", policy)

    # Совместимость: старый per_project_notes → WHAT HAPPENS, если user_brief пуст.
    brief_raw = (user_brief or per_project_notes or "").strip()
    fields = parse_motion_control_user_brief(brief_raw)
    for key, placeholder in _BRIEF_KEY_TO_PLACEHOLDER.items():
        instruction = instruction.replace(placeholder, fields.get(key, ""))

    if has_first_frame:
        # Упрощённый шаблон говорит «2 attachments» — дополняем, иначе Grok игнорирует 3-й still.
        instruction = instruction.replace(
            "I am giving you two attachments:",
            "I am giving you three attachments:",
            1,
        ).replace(
            "2. CHARACTER IMAGE — my character's face, hair and full outfit.\n\nYour job:",
            "2. CHARACTER IMAGE — turnaround sheet: face, hair and full outfit.\n"
            "3. FIRST FRAME IMAGE — opening frame at t=0 (scene, pose, light in context).\n\n"
            "Your job:",
            1,
        )
        instruction = f"{instruction.rstrip()}\n{_FIRST_FRAME_GROK_APPENDIX}"
    return instruction


async def _xai_responses_video_and_images_text(
    *,
    credentials: StudioOpenAiCredentials,
    instruction_text: str,
    file_id: str,
    images: list[tuple[bytes, str]],
    model: str,
    timeout_seconds: float,
    max_completion_tokens: int = 16384,
) -> str:
    import httpx

    root = _api_root_from_v1(credentials.base_url)
    url = f"{root}/responses"
    headers = {
        "Authorization": f"Bearer {credentials.api_key.strip()}",
        "Content-Type": "application/json",
    }
    content: list[dict[str, str]] = [
        {"type": "input_text", "text": instruction_text.strip()},
        {"type": "input_file", "file_id": file_id.strip()},
    ]
    for image_bytes, image_mime in images:
        mime = (image_mime or "image/jpeg").split(";")[0].strip() or "image/jpeg"
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        content.append({"type": "input_image", "image_url": f"data:{mime};base64,{b64}"})
    body = {
        "model": model,
        "input": [{"role": "user", "content": content}],
        "temperature": 0.2,
    }
    if max_completion_tokens > 0:
        body["max_output_tokens"] = max_completion_tokens
    to = max(180.0, float(timeout_seconds))
    async with httpx.AsyncClient(timeout=to) as client:
        r = await client.post(url, headers=headers, json=body)
    raw_snip = (r.text or "")[:2500]
    if r.status_code >= 400:
        raise RuntimeError(f"xAI Responses HTTP {r.status_code}: {raw_snip}")
    payload = r.json()
    return _extract_output_text_from_xai_responses(payload)


async def grok_motion_control_shot_prompt(
    *,
    video_path: Path,
    character_image_bytes: bytes,
    character_image_mime: str = "image/jpeg",
    first_frame_image_bytes: bytes | None = None,
    first_frame_image_mime: str = "image/jpeg",
    credentials: StudioOpenAiCredentials | None = None,
    user_brief: str = "",
    per_project_notes: str = "",
    wants_reference_audio: bool = True,
    has_ref_audio: bool | None = None,
) -> str:
    """
    Анализ performance-видео + CHARACTER IMAGE (+ optional FIRST FRAME) → T2V prompt.
    Без первого кадра: @Image1=character, @Video1=depth.
    С первым кадром: @Image1=opening frame, @Image2=character, @Video1=depth.
    """
    creds = credentials or grok_motion_studio_credentials()
    has_first_frame = bool(first_frame_image_bytes and len(first_frame_image_bytes) >= 64)
    if has_ref_audio is None:
        from app.services.studio_motion_video import probe_video_has_audio

        has_ref_audio = probe_video_has_audio(video_path)
    audio_policy = motion_control_grok_audio_policy(
        wants_reference_audio=wants_reference_audio,
        has_ref_audio=bool(has_ref_audio),
    )
    instruction = apply_motion_control_shot_analyst_instruction(
        load_motion_control_shot_analyst_prompt(),
        audio_policy=audio_policy,
        user_brief=user_brief,
        per_project_notes=per_project_notes,
        has_first_frame=has_first_frame,
    )

    grok_images: list[tuple[bytes, str]] = [
        (character_image_bytes, character_image_mime),
    ]
    if has_first_frame and first_frame_image_bytes is not None:
        grok_images.append((first_frame_image_bytes, first_frame_image_mime))

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
            credentials=creds,
            mp4_path=tmp_mp4,
            timeout_seconds=settings.studio_archive_download_timeout_seconds + 120.0,
        )
        from app.services.studio_grok_motion import _grok_full_video_responses_model

        model = _grok_full_video_responses_model()
        try:
            raw = await _xai_responses_video_and_images_text(
                credentials=creds,
                instruction_text=instruction,
                file_id=file_id_remote,
                images=grok_images,
                model=model,
                timeout_seconds=settings.grok_motion_full_video_timeout_seconds,
                max_completion_tokens=16384,
            )
        except RuntimeError as e:
            # Fallback: video-only timeline + stills in chat.
            log.warning("motion control grok video+images responses failed (%s), fallback chat", str(e)[:200])
            from app.services.studio_grok_motion import grok_step1_timeline_from_video

            timeline = await grok_step1_timeline_from_video(video_path=video_path, credentials=creds)
            from app.services.studio_openai import chat_completion_openai_compatible_text
            from app.services.studio_grok_motion import _grok_fps_stills_model

            fallback_instruction = (
                f"{instruction}\n\n---\n\nREFERENCE VIDEO SUMMARY (fallback timeline):\n{timeline}"
            )
            content: list[dict] = [{"type": "text", "text": fallback_instruction}]
            for img_bytes, img_mime in grok_images:
                mime = (img_mime or "image/jpeg").split(";")[0].strip() or "image/jpeg"
                b64 = base64.standard_b64encode(img_bytes).decode("ascii")
                content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
            raw = await chat_completion_openai_compatible_text(
                model=_grok_fps_stills_model(),
                messages=[{"role": "user", "content": content}],
                max_tokens=16384,
                temperature=0.2,
                credentials=creds,
                timeout_seconds=min(600.0, float(settings.studio_archive_download_timeout_seconds) + 180.0),
            )
        block = extract_shot_analyst_prompt_block(raw)
        if len(block) < 120:
            raise RuntimeError("Grok вернул слишком короткий промпт для видео.")
        bound = bind_motion_control_seedance_tags(block, has_first_frame=has_first_frame)
        log.info(
            "motion control grok prompt chars=%s dur=%s audio_policy=%s first_frame=%s",
            len(bound),
            probe_video_duration_seconds(video_path),
            audio_policy,
            has_first_frame,
        )
        return bound
    finally:
        if tmp_mp4 is not None:
            tmp_mp4.unlink(missing_ok=True)
        if file_id_remote:
            await _xai_delete_file_maybe(
                credentials=creds,
                file_id=file_id_remote,
                timeout_seconds=min(120.0, settings.studio_archive_download_timeout_seconds),
            )
