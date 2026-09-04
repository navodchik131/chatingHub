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
from typing import Any

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


def probe_video_has_audio(video_path: Path) -> bool:
    try:
        r = subprocess.run(
            [
                _ffprobe_bin(),
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        name = (r.stdout or "").strip().lower()
        return r.returncode == 0 and bool(name)
    except Exception:
        return False


def strip_video_audio_bytes(data: bytes) -> bytes:
    """Убирает аудиодорожку из mp4 — для video-edit, когда звук приклеим после генерации."""
    if not data or len(data) < 256:
        return data
    fd_in, in_path_str = tempfile.mkstemp(prefix="strip_in_", suffix=".mp4")
    os.close(fd_in)
    fd_out, out_path_str = tempfile.mkstemp(prefix="strip_out_", suffix=".mp4")
    os.close(fd_out)
    in_path = Path(in_path_str)
    out_path = Path(out_path_str)
    try:
        in_path.write_bytes(data)
        if not probe_video_has_audio(in_path):
            return data
        cmd = [
            _ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(in_path),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        r = subprocess.run(cmd, check=False, timeout=300, capture_output=True)
        if r.returncode != 0 or not out_path.is_file() or out_path.stat().st_size < 256:
            log_motion.warning(
                "strip video audio failed: %s",
                (r.stderr or b"").decode("utf-8", errors="replace")[:400],
            )
            return data
        return out_path.read_bytes()
    except Exception:
        log_motion.warning("strip video audio failed", exc_info=True)
        return data
    finally:
        in_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)


def mux_original_audio_onto_video(video_path: Path, audio_source: Path) -> bool:
    """Накладывает аудио из исходника на уже готовый ролик (без перекодирования картинки)."""
    if not video_path.is_file() or not audio_source.is_file():
        return False
    if not probe_video_has_audio(audio_source):
        return False
    if probe_video_has_audio(video_path):
        return True
    fd, tmp_path_str = tempfile.mkstemp(prefix="motion_mux_", suffix=".mp4")
    os.close(fd)
    tmp_path = Path(tmp_path_str)
    try:
        cmd = [
            _ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_source),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-shortest",
            "-movflags",
            "+faststart",
            str(tmp_path),
        ]
        r = subprocess.run(cmd, check=False, timeout=600, capture_output=True)
        if r.returncode != 0 or not tmp_path.is_file() or tmp_path.stat().st_size < 1024:
            log_motion.warning(
                "motion audio mux failed: %s",
                (r.stderr or b"").decode("utf-8", errors="replace")[:800],
            )
            tmp_path.unlink(missing_ok=True)
            return False
        video_path.unlink(missing_ok=True)
        tmp_path.replace(video_path)
        return probe_video_has_audio(video_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        log_motion.warning("motion audio mux failed", exc_info=True)
        return False


def _owner_motion_dir(owner_id: int) -> Path:
    owner_dir = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    root = MOTION_VIDEO_ROOT.resolve()
    if not str(owner_dir).startswith(str(root)):
        raise RuntimeError("invalid motion video path")
    owner_dir.mkdir(parents=True, exist_ok=True)
    return owner_dir


def resolve_motion_audio_file(owner_id: int, file_id: str) -> Path | None:
    fid = str(file_id or "").strip()[:128]
    if not fid:
        return None
    try:
        base = _owner_motion_dir(owner_id)
    except RuntimeError:
        return None
    for name in (f"{fid}.audio.mp3", f"{fid}.audio.wav"):
        path = base / name
        if path.is_file() and path.stat().st_size > 256:
            rp = path.resolve()
            if str(rp).startswith(str(base)):
                return rp
    return None


def extract_motion_audio_file(
    *,
    owner_id: int,
    file_id: str,
    source: Path,
    target_sec: int | None = None,
) -> Path | None:
    """Вынимает звук исходника в mp3/wav рядом с motion-файлом — для Seedance @Audio1."""
    fid = str(file_id or "").strip()[:128]
    if not fid or not source.is_file() or not probe_video_has_audio(source):
        return None
    existing = resolve_motion_audio_file(owner_id, fid)
    if existing is not None and not target_sec:
        return existing
    if existing is not None:
        existing.unlink(missing_ok=True)
    dest_mp3 = _owner_motion_dir(owner_id) / f"{fid}.audio.mp3"
    dest_wav = _owner_motion_dir(owner_id) / f"{fid}.audio.wav"
    dur_args: list[str] = []
    if target_sec and int(target_sec) > 0:
        target = max(1, min(30, int(target_sec)))
        src_dur = probe_video_duration_seconds(source) or 0.0
        if src_dur > target + 0.25:
            dur_args.extend(["-t", str(target)])
        elif src_dur > 0 and src_dur < target - 0.25:
            pad = max(0.05, target - src_dur)
            dur_args.extend(["-af", f"apad=pad_dur={pad:.3f}", "-t", str(target)])
    attempts: list[tuple[Path, list[str]]] = [
        (dest_mp3, ["-c:a", "libmp3lame", "-q:a", "4", "-ac", "2", "-ar", "44100"]),
        (dest_wav, ["-c:a", "pcm_s16le", "-ac", "2", "-ar", "44100"]),
    ]
    for dest, codec in attempts:
        dest.unlink(missing_ok=True)
        cmd = [
            _ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            *dur_args,
            *codec,
            str(dest),
        ]
        try:
            r = subprocess.run(cmd, check=False, timeout=180, capture_output=True)
        except Exception:
            dest.unlink(missing_ok=True)
            continue
        if r.returncode == 0 and dest.is_file() and dest.stat().st_size > 256:
            log_motion.info("motion audio extracted file_id=%s dest=%s", fid, dest.name)
            return dest
        dest.unlink(missing_ok=True)
    log_motion.warning("motion audio extract failed file_id=%s", fid)
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

    has_audio = probe_video_has_audio(source)
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
            if has_audio:
                cmd.extend(["-af", f"apad=pad_dur={pad:.3f}"])
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
            ]
        )
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.append("-an")
        cmd.append(str(out_path))
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
    audio_src = resolve_motion_video_source(owner_id, file_id) or source_path
    mux_original_audio_onto_video(source_path, audio_src)
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
                mux_original_audio_onto_video(out_path, audio_src)
        extract_motion_audio_file(
            owner_id=owner_id,
            file_id=out_id,
            source=audio_src,
            target_sec=target_sec,
        )
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


def resolve_motion_video_source(owner_id: int, file_id: str) -> Path | None:
    """Исходник до outline-обработки ({file_id}.source.ext)."""
    root = MOTION_VIDEO_ROOT.resolve()
    base = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    if not str(base).startswith(str(root)) or not base.is_dir():
        return None
    fid = str(file_id).strip()[:128]
    if not fid:
        return None
    for p in base.glob(f"{fid}.source.*"):
        if p.is_file() and p.suffix.lower() in _VIDEO_SUFFIX:
            rp = p.resolve()
            if str(rp).startswith(str(base)):
                return rp
    return None


def resolve_motion_video_uploaded(owner_id: int, file_id: str) -> Path | None:
    """Готовый outline/legacy upload или исходник, ожидающий outline при генерации."""
    path = resolve_motion_video_file(owner_id, file_id)
    if path is not None:
        return path
    return resolve_motion_video_source(owner_id, file_id)


def motion_outline_requested(params: dict[str, Any]) -> bool:
    """Нужна ли contour/silhouette-обработка референс-видеo для этой задачи."""
    from app.config import settings

    mc_wizard = str(params.get("motion_control_wizard") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    # Motion Control wizard v2: depth map + Grok — без rembg/outline.
    if mc_wizard:
        return False
    return bool(settings.motion_outline_enabled)


def resolve_motion_video_for_render(
    owner_id: int,
    file_id: str,
    *,
    use_outline: bool,
) -> Path | None:
    """Цветной исходник или outline-версия — в зависимости от флага."""
    if use_outline:
        return resolve_motion_video_file(owner_id, file_id) or resolve_motion_video_source(
            owner_id, file_id
        )
    return resolve_motion_video_source(owner_id, file_id) or resolve_motion_video_file(
        owner_id, file_id
    )


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


