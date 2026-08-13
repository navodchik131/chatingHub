"""Временные driving-video для Kling Motion Control (файл на диске + публичный JWT URL)."""

from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from app.config import BACKEND_DIR, settings

MOTION_VIDEO_ROOT = (BACKEND_DIR / "data" / "studio_motion_videos").resolve()

_VIDEO_SUFFIX = {".mp4", ".webm", ".mov", ".m4v"}
log_motion = logging.getLogger(__name__)


def _ffmpeg_bin() -> str:
    raw = (settings.ffmpeg_binary or "").strip() or "ffmpeg"
    p = Path(raw)
    if p.is_file():
        return str(p.resolve())
    exe = shutil.which(raw)
    if exe:
        return exe
    raise RuntimeError(
        f"Не найден ffmpeg («{raw}»). Установите пакет ffmpeg в контейнере/на сервере или задайте FFMPEG_BINARY "
        "(например /usr/bin/ffmpeg) в backend/.env. В Docker: пересоберите образ с Dockerfile, где ставится ffmpeg."
    )


def _ffprobe_bin() -> str:
    """Рядом с ffmpeg (официальный биндинг Windows/Linux) или ffprobe из PATH."""
    ffmpeg_path = Path(_ffmpeg_bin())
    sibling = ffmpeg_path.parent / (
        "ffprobe.exe" if ffmpeg_path.name.lower().endswith(".exe") else "ffprobe"
    )
    if sibling.is_file():
        return str(sibling.resolve())
    wh = shutil.which("ffprobe")
    if wh:
        return wh
    raise RuntimeError(
        "Не найден ffprobe рядом с ffmpeg. Установите полный набор ffmpeg (обычно включает ffprobe) или добавьте ffprobe в PATH."
    )


def probe_video_duration_seconds(video_path: Path) -> float | None:
    """Длительность ролика в секундах; None если ffprobe не смог."""
    try:
        r = subprocess.run(
            [
                _ffprobe_bin(),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return float(str(r.stdout).strip())
    except Exception:
        return None


def fit_motion_video_to_duration(source: Path, target_sec: int) -> tuple[Path, bool]:
    """
    Подгоняет референс под целевую длительность: обрезка или дополнение последним кадром.
    Возвращает (path, is_temp). При is_temp=True вызывающий код должен удалить файл.
    """
    target = max(1, min(30, int(target_sec)))
    src_dur = probe_video_duration_seconds(source)
    if src_dur is None or src_dur <= 0:
        return source, False
    if abs(src_dur - target) < 0.35:
        return source, False

    fd, tmp_path_str = tempfile.mkstemp(prefix="motion_fit_", suffix=".mp4")
    os.close(fd)
    out_path = Path(tmp_path_str)
    try:
        cmd: list[str] = [
            _ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
        ]
        if src_dur > target + 0.25:
            cmd.extend(["-t", str(target)])
        else:
            pad = max(0.05, target - src_dur)
            cmd.extend(["-vf", f"tpad=stop_mode=clone:stop_duration={pad:.3f}"])
        cmd.extend(
            [
                "-movflags",
                "+faststart",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(out_path),
            ]
        )
        subprocess.run(cmd, check=True, timeout=600, capture_output=True)
        log_motion.info(
            "motion video fit %.2fs -> %ss (src=%.2fs)",
            src_dur,
            target,
            src_dur,
        )
        return out_path, True
    except Exception:
        out_path.unlink(missing_ok=True)
        log_motion.warning("motion video fit failed, using source as-is", exc_info=True)
        return source, False


def prepare_motion_video_file_for_duration(
    *,
    owner_id: int,
    file_id: str,
    source_path: Path,
    target_sec: int,
) -> tuple[str, Path, int | None]:
    """
    При необходимости подгоняет длительность и сохраняет копию на диск.
    Возвращает (file_id_for_url, path_on_disk, duration_sec).
    """
    fit_path, is_temp = fit_motion_video_to_duration(source_path, target_sec)
    out_id = file_id
    out_path = source_path
    try:
        if is_temp:
            out_id = save_motion_video_bytes(
                owner_id=owner_id,
                raw=fit_path.read_bytes(),
                filename=f"motion_{target_sec}s.mp4",
            )
            resolved = resolve_motion_video_file(owner_id, out_id)
            if resolved is not None:
                out_path = resolved
        probed = probe_video_duration_seconds(out_path)
        dur = int(math.ceil(probed)) if probed and probed > 0 else int(target_sec)
        return out_id, out_path, dur
    finally:
        if is_temp:
            fit_path.unlink(missing_ok=True)


def extract_video_timeline_frames_jpeg(
    video_path: Path,
    *,
    max_seconds: int = 30,
    max_width: int = 768,
) -> tuple[list[bytes], float]:
    """
    До ``max_seconds`` кадров с частотой 1 Гц (метка времени ~= индекс секунды от начала ролика).
    Второй элемент — нижняя оценка длительности (по метаданным или числу кадров).
    """
    cap = max(1, min(120, max_seconds))
    dur = probe_video_duration_seconds(video_path)
    frames_target = cap
    if dur is not None and dur > 0:
        frames_target = min(cap, max(1, int(dur) + 1))
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        pattern = str(tdir / "sec%03d.jpg")
        # scale: ужимаем по ширине для лимитов vision API
        vf = f"fps=1,scale=min({max_width}\\,iw):-2"
        subprocess.run(
            [
                _ffmpeg_bin(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(video_path),
                "-vf",
                vf,
                "-frames:v",
                str(frames_target),
                pattern,
            ],
            check=True,
            timeout=300,
            capture_output=True,
        )
        paths = sorted(tdir.glob("sec*.jpg"))
        out_frames = [p.read_bytes() for p in paths if p.is_file()]
    span_sec = dur if dur is not None and dur > 0 else float(len(out_frames))
    return out_frames, float(min(span_sec, float(len(out_frames)) or span_sec))


def _ext_for_filename(name: str | None) -> str:
    if not name:
        return ".mp4"
    suf = Path(name).suffix.lower()
    return suf if suf in _VIDEO_SUFFIX else ".mp4"


def save_motion_video_bytes(*, owner_id: int, raw: bytes, filename: str | None) -> str:
    """Сохраняет видео, возвращает file_id (stem) для JWT."""
    file_id = uuid.uuid4().hex
    ext = _ext_for_filename(filename)
    owner_dir = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    if not str(owner_dir).startswith(str(MOTION_VIDEO_ROOT)):
        raise RuntimeError("invalid motion video path")
    owner_dir.mkdir(parents=True, exist_ok=True)
    path = owner_dir / f"{file_id}{ext}"
    path.write_bytes(raw)
    return file_id


def resolve_motion_video_file(owner_id: int, file_id: str) -> Path | None:
    root = MOTION_VIDEO_ROOT.resolve()
    base = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    if not str(base).startswith(str(root)) or not base.is_dir():
        return None
    fid = str(file_id).strip()[:128]
    if not fid:
        return None
    preferred = base / f"{fid}.mp4"
    if preferred.is_file():
        rp = preferred.resolve()
        if str(rp).startswith(str(base)):
            return rp
    for p in base.glob(f"{fid}.*"):
        if not p.is_file():
            continue
        if ".source." in p.name.lower():
            continue
        rp = p.resolve()
        if not str(rp).startswith(str(base)):
            continue
        if p.suffix.lower() in _VIDEO_SUFFIX:
            return rp
    return None


def extract_first_frame_jpeg(video_path: Path) -> bytes:
    """Первый кадр ролика — для референса позы (Nano Banana) и опционально vision."""
    out: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            out = Path(tmp.name)
        subprocess.run(
            [
                _ffmpeg_bin(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(video_path),
                "-vf",
                "select=eq(n\\,0)",
                "-vframes",
                "1",
                "-q:v",
                "3",
                str(out),
            ],
            check=True,
            timeout=120,
            capture_output=True,
        )
        return out.read_bytes()
    finally:
        if out is not None:
            out.unlink(missing_ok=True)


def extract_video_sample_frames_jpeg(video_path: Path, *, max_frames: int = 4) -> list[bytes]:
    """Несколько кадров (равномерно по времени) — для LLM-описания движения."""
    capped = max(1, min(8, max_frames))
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        pattern = str(tdir / "f%03d.jpg")
        subprocess.run(
            [
                _ffmpeg_bin(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(video_path),
                "-vf",
                "fps=1/2",
                "-frames:v",
                str(capped),
                pattern,
            ],
            check=True,
            timeout=180,
            capture_output=True,
        )
        paths = sorted(tdir.glob("f*.jpg"))
        return [p.read_bytes() for p in paths if p.is_file()]


def transcode_motion_video_mp4_under_size(
    source: Path,
    *,
    max_duration_sec: int,
    target_max_bytes: int,
    filename_hint: str = "motion_clip.mp4",
) -> Path:
    """
    Готовит короткий H.264+AAC MP4 для загрузки в xAI Files (обычный лимит ~48–50 MiB).

    Прогрессивное уменьшение ширины/CRF пока файл не впишется в лимит.
    Вызывающий код обязан удалить возвращённый путь после использования.
    """
    cap = max(1, min(120, int(max_duration_sec)))
    max_w_candidates = [960, 848, 720, 544, 480]
    crf_candidates = [24, 26, 28, 30, 32, 34]
    last_err_stderr: bytes = b""
    _ = filename_hint

    for max_w in max_w_candidates:
        for crf in crf_candidates:
            fd, tmp_path_str = tempfile.mkstemp(prefix="grok_motion_", suffix=".mp4")
            os.close(fd)
            out_path = Path(tmp_path_str)
            try:
                r = subprocess.run(
                    [
                        _ffmpeg_bin(),
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        str(source),
                        "-t",
                        str(cap),
                        "-vf",
                        f"scale=min({max_w}\\,iw):-2",
                        "-movflags",
                        "+faststart",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        str(crf),
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "96k",
                        "-ac",
                        "1",
                        str(out_path),
                    ],
                    check=False,
                    timeout=600,
                    capture_output=True,
                )
                if r.returncode != 0:
                    last_err_stderr = (r.stderr or b"")[-900:]
                    out_path.unlink(missing_ok=True)
                    continue
                sz = out_path.stat().st_size
                if sz <= target_max_bytes:
                    log_motion.info(
                        "motion transcode for Grok upload: %.2f MiB (w≤%s crf=%s cap=%ss)",
                        sz / (1024 * 1024),
                        max_w,
                        crf,
                        cap,
                    )
                    return out_path
                out_path.unlink(missing_ok=True)
            except BaseException:
                out_path.unlink(missing_ok=True)
                raise

    stderr_hint = (
        last_err_stderr.decode(errors="replace")[:512] if last_err_stderr else "(нет stderr)"
    )
    raise RuntimeError(
        "Не удалось уместить сжатый клип видео в лимит xAI Files или ffmpeg вернул ошибку. "
        f"Лимит {target_max_bytes} байт, дли́тельность не более {cap} с. Последнее stderr ffmpeg: {stderr_hint}"
    )


