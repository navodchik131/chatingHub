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


def bind_motion_control_seedance_tags(prompt: str) -> str:
    """Подставляем @Video1/@Image1 вместо плейсхолдеров Grok."""
    out = (prompt or "").strip()
    out = out.replace("<<<DEPTH_MAP>>>", "@Video1")
    out = out.replace("<<<CHARACTER_IMAGE>>>", "@Image1")
    return out


async def _xai_responses_video_and_image_text(
    *,
    credentials: StudioOpenAiCredentials,
    instruction_text: str,
    file_id: str,
    image_bytes: bytes,
    image_mime: str,
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
    mime = (image_mime or "image/jpeg").split(";")[0].strip() or "image/jpeg"
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": instruction_text.strip()},
                    {"type": "input_file", "file_id": file_id.strip()},
                    {"type": "input_image", "image_url": f"data:{mime};base64,{b64}"},
                ],
            }
        ],
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
    credentials: StudioOpenAiCredentials | None = None,
    per_project_notes: str = "",
) -> str:
    """
    Анализ performance-видео + CHARACTER IMAGE → готовый T2V prompt (English).
    Возвращает текст с @Video1 (depth) и @Image1 (character).
    """
    creds = credentials or grok_motion_studio_credentials()
    instruction = load_motion_control_shot_analyst_prompt()
    notes = (per_project_notes or "").strip()
    if notes:
        instruction = f"{instruction}\n\n## PER-PROJECT NOTES\n\n{notes}"

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
            raw = await _xai_responses_video_and_image_text(
                credentials=creds,
                instruction_text=instruction,
                file_id=file_id_remote,
                image_bytes=character_image_bytes,
                image_mime=character_image_mime,
                model=model,
                timeout_seconds=settings.grok_motion_full_video_timeout_seconds,
                max_completion_tokens=16384,
            )
        except RuntimeError as e:
            # Fallback: video-only timeline + character image in chat (без native image slot).
            log.warning("motion control grok video+image responses failed (%s), fallback chat", str(e)[:200])
            from app.services.studio_grok_motion import grok_step1_timeline_from_video

            timeline = await grok_step1_timeline_from_video(video_path=video_path, credentials=creds)
            from app.services.studio_openai import chat_completion_openai_compatible_text
            from app.services.studio_grok_motion import _grok_fps_stills_model

            mime = (character_image_mime or "image/jpeg").split(";")[0].strip() or "image/jpeg"
            b64 = base64.standard_b64encode(character_image_bytes).decode("ascii")
            fallback_instruction = (
                f"{instruction}\n\n---\n\nREFERENCE VIDEO SUMMARY (fallback timeline):\n{timeline}"
            )
            content = [
                {"type": "text", "text": fallback_instruction},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]
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
        bound = bind_motion_control_seedance_tags(block)
        log.info("motion control grok prompt chars=%s dur=%s", len(bound), probe_video_duration_seconds(video_path))
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
