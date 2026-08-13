"""Контурный (edge-outline) motion-референс через ffmpeg — сохраняет движение, убивает личность."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from app.config import BACKEND_DIR, settings
from app.services.studio_motion_video import (
    _ext_for_filename,
    _ffmpeg_bin,
    _ffprobe_bin,
    resolve_motion_video_file,
    resolve_motion_video_source,
)

log = logging.getLogger(__name__)

OUTLINE_CACHE_ROOT = (BACKEND_DIR / "data" / "motion_outline_cache").resolve()

MOTION_OUTLINE_VIDEO_PROMPT_TEMPLATE = (
    "@Video1 is a blurred edge-outline motion reference. It carries camera "
    "path, framing, timing, body movement and gesture only — it contains no "
    "readable face, hair, skin or clothing detail by construction. "
    "All appearance comes from {appearance_refs}."
)

_RENDER_SEM = threading.Semaphore(max(1, int(getattr(settings, "motion_outline_max_parallel", 1) or 1)))


@dataclass(frozen=True)
class MotionVideoInputMeta:
    width: int
    height: int
    duration_sec: float
    content_sha256: str


@dataclass(frozen=True)
class EdgeOutlineParams:
    sigma: float
    low: float
    high: float
    out_w: int
    out_h: int
    pre_scale_w: int = 360


@dataclass
class MotionOutlineProcessResult:
    outline_path: Path
    params: EdgeOutlineParams
    face_detection_warning: bool = False
    from_cache: bool = False


def assert_ffmpeg_tools_available() -> None:
    """Проверка ffmpeg/ffprobe при старте приложения."""
    _ffmpeg_bin()
    _ffprobe_bin()


def motion_outline_video_prompt_block(*, appearance_refs: str) -> str:
    refs = (appearance_refs or "@Image1").strip()
    return MOTION_OUTLINE_VIDEO_PROMPT_TEMPLATE.format(appearance_refs=refs)


def _run_cmd(
    cmd: list[str],
    *,
    timeout: float,
    binary_stdout: bool = False,
) -> subprocess.CompletedProcess[str | bytes]:
    if binary_stdout:
        return subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _stderr_text(proc: subprocess.CompletedProcess[str | bytes]) -> str:
    err = proc.stderr
    if err is None:
        return ""
    if isinstance(err, bytes):
        return err.decode("utf-8", errors="replace")
    return err


def _moov_valid(path: Path) -> bool:
    try:
        r = _run_cmd(
            [
                _ffprobe_bin(),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            timeout=60,
        )
        if r.returncode != 0:
            err = _stderr_text(r).lower()
            if "moov atom not found" in err:
                return False
            return False
        return float(str(r.stdout).strip()) > 0
    except Exception:
        return False


def probe_motion_video_stream(path: Path) -> tuple[int, int, float]:
    r = _run_cmd(
        [
            _ffprobe_bin(),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        timeout=60,
    )
    if r.returncode != 0:
        err = _stderr_text(r).strip()
        if "moov atom not found" in err.lower():
            raise RuntimeError("Файл видео повреждён или не докачан (moov atom not found).")
        raise RuntimeError(f"Не удалось прочитать видео: {err[:500] or r.returncode}")
    try:
        stdout = r.stdout if isinstance(r.stdout, str) else (r.stdout or b"").decode("utf-8", errors="replace")
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError as e:
        raise RuntimeError("Не удалось прочитать метаданные видео.") from e
    streams = payload.get("streams")
    if not isinstance(streams, list) or not streams:
        raise RuntimeError("В файле нет видеодорожки.")
    stream0 = streams[0] if isinstance(streams[0], dict) else {}
    try:
        w = int(stream0.get("width") or 0)
        h = int(stream0.get("height") or 0)
    except (TypeError, ValueError) as e:
        raise RuntimeError("Не удалось прочитать размер кадра видео.") from e
    fmt = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    try:
        dur = float(fmt.get("duration") or 0)
    except (TypeError, ValueError) as e:
        raise RuntimeError("Не удалось прочитать длительность видео.") from e
    if w <= 0 or h <= 0 or dur <= 0:
        raise RuntimeError("Видеодорожка пустая или повреждена.")
    return w, h, dur


def validate_motion_video_upload(path: Path, *, raw_size: int) -> MotionVideoInputMeta:
    max_mb = min(200, max(1, int(settings.studio_motion_max_upload_mb)))
    max_bytes = max_mb * 1024 * 1024
    if raw_size > max_bytes:
        raise RuntimeError(f"Видео слишком большое (макс. {max_mb} МБ).")
    if raw_size < 1024:
        raise RuntimeError("Пустой файл видео.")

    suf = path.suffix.lower()
    if suf and suf not in {".mp4", ".mov", ".webm", ".m4v"}:
        raise RuntimeError("Поддерживаются только MP4, MOV и WebM.")

    if not _moov_valid(path):
        raise RuntimeError("Файл видео повреждён или не докачан.")

    w, h, dur = probe_motion_video_stream(path)
    max_dur = max(1, int(settings.motion_outline_max_duration_sec))
    if dur > max_dur + 0.05:
        raise RuntimeError(f"Референс-видео длиннее {max_dur} с — сократите клип.")

    content_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return MotionVideoInputMeta(
        width=w,
        height=h,
        duration_sec=dur,
        content_sha256=content_sha256,
    )


def output_size_for_source(width: int, height: int) -> tuple[int, int]:
    w, h = int(width), int(height)
    if h > w:
        return 540, 960
    if w > h:
        return 960, 540
    return 720, 720


def choose_edge_params(stddev: float) -> tuple[float, float, float]:
    s = float(stddev)
    if s < 35:
        return 1.6, 0.04, 0.12
    if s > 70:
        return 0.8, 0.10, 0.30
    return 1.0, 0.06, 0.18


def measure_gray_stats(path: Path) -> tuple[float, float]:
    r = _run_cmd(
        [
            _ffmpeg_bin(),
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            "fps=1,scale=64:-2,format=gray",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        timeout=120,
        binary_stdout=True,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"Не удалось проанализировать яркость видео: {_stderr_text(r)[:400]}"
        )
    data = r.stdout if isinstance(r.stdout, (bytes, bytearray)) else b""
    if len(data) < 64:
        raise RuntimeError("Не удалось проанализировать яркость видео (мало данных).")
    vals = list(data)
    n = len(vals)
    mean = sum(vals) / n
    var = sum((x - mean) ** 2 for x in vals) / n
    return mean, math.sqrt(var)


def _cache_key(meta: MotionVideoInputMeta, params: EdgeOutlineParams) -> str:
    raw = (
        f"{meta.content_sha256}|{params.sigma}|{params.low}|{params.high}|"
        f"{params.out_w}|{params.out_h}|{params.pre_scale_w}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_paths(key: str) -> tuple[Path, Path]:
    OUTLINE_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return OUTLINE_CACHE_ROOT / f"{key}.mp4", OUTLINE_CACHE_ROOT / f"{key}.json"


def _load_cached_outline(key: str) -> Path | None:
    mp4, meta = _cache_paths(key)
    if not mp4.is_file() or mp4.stat().st_size < 1024:
        return None
    if not _moov_valid(mp4):
        mp4.unlink(missing_ok=True)
        meta.unlink(missing_ok=True)
        return None
    return mp4


def _save_cache(key: str, outline: Path, params: EdgeOutlineParams, meta: MotionVideoInputMeta) -> None:
    mp4, jpath = _cache_paths(key)
    shutil.copy2(outline, mp4)
    jpath.write_text(
        json.dumps(
            {
                "content_sha256": meta.content_sha256,
                "sigma": params.sigma,
                "low": params.low,
                "high": params.high,
                "out_w": params.out_w,
                "out_h": params.out_h,
                "pre_scale_w": params.pre_scale_w,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _build_vf(params: EdgeOutlineParams) -> str:
    p = params
    return (
        f"scale={p.pre_scale_w}:-2,gblur=sigma={p.sigma},"
        f"edgedetect=low={p.low}:high={p.high},negate,"
        f"scale={p.out_w}:{p.out_h}:flags=bilinear"
    )


def _render_outline(source: Path, dest: Path, params: EdgeOutlineParams) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    cmd = [
        _ffmpeg_bin(),
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-vf",
        _build_vf(params),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
        "-pix_fmt",
        "yuv420p",
        str(dest),
    ]
    timeout = max(30, int(settings.motion_outline_render_timeout_sec))
    r = _run_cmd(cmd, timeout=timeout)
    if r.returncode != 0:
        log.error("motion outline ffmpeg failed: %s", _stderr_text(r)[:2000])
        dest.unlink(missing_ok=True)
        raise RuntimeError("Не удалось обработать референс-видео. Попробуйте другой файл.")
    if not dest.is_file() or dest.stat().st_size < 1024:
        dest.unlink(missing_ok=True)
        raise RuntimeError("Обработка видео не дала результата.")
    if not _moov_valid(dest):
        dest.unlink(missing_ok=True)
        raise RuntimeError("Обработка видео прервалась — файл битый. Повторите загрузку.")


def _mean_adjacent_frame_delta(path: Path) -> float:
    r = _run_cmd(
        [
            _ffmpeg_bin(),
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            "fps=6,scale=64:-2",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        timeout=120,
        binary_stdout=True,
    )
    if r.returncode != 0:
        return 0.0
    data = r.stdout if isinstance(r.stdout, (bytes, bytearray)) else b""
    frame_size = 64 * 64
    if len(data) < frame_size * 2:
        return 0.0
    n_frames = len(data) // frame_size
    if n_frames < 2:
        return 0.0
    deltas: list[float] = []
    prev = data[:frame_size]
    for i in range(1, n_frames):
        cur = data[i * frame_size : (i + 1) * frame_size]
        if len(cur) < frame_size:
            break
        s = sum(abs(a - b) for a, b in zip(cur, prev)) / frame_size
        deltas.append(s)
        prev = cur
    return sum(deltas) / len(deltas) if deltas else 0.0


def _extract_sample_jpegs(path: Path, count: int = 10) -> list[bytes]:
    dur_r = _run_cmd(
        [
            _ffprobe_bin(),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        timeout=30,
    )
    try:
        dur = float(str(dur_r.stdout).strip())
    except (TypeError, ValueError):
        dur = 5.0
    dur = max(0.5, dur)
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        frames: list[bytes] = []
        for i in range(max(1, count)):
            t = min(dur - 0.05, (dur * i) / max(1, count - 1)) if count > 1 else 0.0
            out = tdir / f"f{i:02d}.jpg"
            r = _run_cmd(
                [
                    _ffmpeg_bin(),
                    "-v",
                    "error",
                    "-ss",
                    f"{t:.3f}",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "5",
                    str(out),
                ],
                timeout=60,
            )
            if r.returncode == 0 and out.is_file() and out.stat().st_size > 64:
                frames.append(out.read_bytes())
        return frames


def _detect_face_in_jpeg(jpeg: bytes) -> bool:
    try:
        import cv2  # type: ignore
        import numpy as np
    except ImportError:
        return False
    try:
        cascade_cls = getattr(cv2, "CascadeClassifier", None)
        if cascade_cls is None:
            return False
        data = getattr(cv2, "data", None)
        haarcascades = getattr(data, "haarcascades", "") if data is not None else ""
        if not haarcascades:
            return False
        arr = np.frombuffer(jpeg, dtype=np.uint8)
        imdecode = getattr(cv2, "imdecode", None)
        if imdecode is None:
            return False
        img = imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return False
        cascade_path = haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cascade_cls(cascade_path)
        if cascade.empty():
            return False
        faces = cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=4, minSize=(24, 24))
        return len(faces) > 0
    except Exception:
        log.warning("motion outline face check skipped", exc_info=True)
        return False


def _faces_detected_in_video(path: Path) -> bool:
    try:
        for frame in _extract_sample_jpegs(path, count=10):
            if _detect_face_in_jpeg(frame):
                return True
    except Exception:
        log.warning("motion outline face scan failed", exc_info=True)
    return False


def _validate_outline_output(source_dur: float, outline: Path) -> None:
    if not _moov_valid(outline):
        raise RuntimeError("Обработанное видео битое (moov atom not found).")
    _, _, out_dur = probe_motion_video_stream(outline)
    if abs(out_dur - source_dur) > 0.35:
        raise RuntimeError(
            f"Длительность после обработки не совпадает ({out_dur:.1f} с vs {source_dur:.1f} с)."
        )
    motion = _mean_adjacent_frame_delta(outline)
    if motion < 0.35:
        raise RuntimeError("После обработки видео выглядит статичным — проверьте исходник.")


def try_motion_outline_from_cache(source: Path) -> MotionOutlineProcessResult | None:
    """Быстрый cache-hit без ffmpeg-рендера."""
    meta = validate_motion_video_upload(source, raw_size=source.stat().st_size)
    _, stddev = measure_gray_stats(source)
    sigma, low, high = choose_edge_params(stddev)
    out_w, out_h = output_size_for_source(meta.width, meta.height)
    params = EdgeOutlineParams(sigma=sigma, low=low, high=high, out_w=out_w, out_h=out_h)
    cache_key = _cache_key(meta, params)
    cached = _load_cached_outline(cache_key)
    if cached is None:
        return None
    fd, tmp = tempfile.mkstemp(prefix="motion_outline_", suffix=".mp4")
    os.close(fd)
    tmp_path = Path(tmp)
    shutil.copy2(cached, tmp_path)
    return MotionOutlineProcessResult(outline_path=tmp_path, params=params, from_cache=True)


def process_motion_video_outline(source: Path) -> MotionOutlineProcessResult:
    """Синхронная обработка (вызывать из worker/thread)."""
    meta = validate_motion_video_upload(source, raw_size=source.stat().st_size)
    _, stddev = measure_gray_stats(source)
    sigma, low, high = choose_edge_params(stddev)
    out_w, out_h = output_size_for_source(meta.width, meta.height)
    params = EdgeOutlineParams(sigma=sigma, low=low, high=high, out_w=out_w, out_h=out_h)

    cache_key = _cache_key(meta, params)
    cached = _load_cached_outline(cache_key)
    if cached is not None:
        fd, tmp = tempfile.mkstemp(prefix="motion_outline_", suffix=".mp4")
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            shutil.copy2(cached, tmp_path)
            return MotionOutlineProcessResult(
                outline_path=tmp_path,
                params=params,
                from_cache=True,
            )
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    face_warning = False
    last_err: Exception | None = None
    attempt_params = [params]
    if params.pre_scale_w > 240:
        attempt_params.append(
            EdgeOutlineParams(
                sigma=max(params.sigma, 1.8),
                low=params.low,
                high=params.high,
                out_w=params.out_w,
                out_h=params.out_h,
                pre_scale_w=240,
            )
        )

    outline_path: Path | None = None
    used_params = params
    for attempt_idx, p in enumerate(attempt_params[:2]):
        fd, tmp = tempfile.mkstemp(prefix="motion_outline_", suffix=".mp4")
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            with _RENDER_SEM:
                _render_outline(source, tmp_path, p)
            _validate_outline_output(meta.duration_sec, tmp_path)
            if _faces_detected_in_video(tmp_path):
                if attempt_idx + 1 < len(attempt_params):
                    tmp_path.unlink(missing_ok=True)
                    continue
                face_warning = True
            outline_path = tmp_path
            used_params = p
            break
        except Exception as e:
            last_err = e
            tmp_path.unlink(missing_ok=True)
            if attempt_idx + 1 >= len(attempt_params):
                raise
    if outline_path is None:
        raise last_err or RuntimeError("Не удалось обработать референс-видео.")

    if not used_params == params or not _load_cached_outline(_cache_key(meta, used_params)):
        try:
            _save_cache(_cache_key(meta, used_params), outline_path, used_params, meta)
        except Exception:
            log.warning("motion outline cache save failed", exc_info=True)

    return MotionOutlineProcessResult(
        outline_path=outline_path,
        params=used_params,
        face_detection_warning=face_warning,
        from_cache=False,
    )


def save_motion_video_source_bytes(*, owner_id: int, raw: bytes, filename: str | None) -> str:
    """Сохраняет исходник; outline появится при генерации (ensure_motion_outline_ready)."""
    import uuid

    from app.services.studio_motion_video import MOTION_VIDEO_ROOT

    file_id = uuid.uuid4().hex
    ext = _ext_for_filename(filename)
    owner_dir = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    root = MOTION_VIDEO_ROOT.resolve()
    if not str(owner_dir).startswith(str(root)):
        raise RuntimeError("invalid motion video path")
    owner_dir.mkdir(parents=True, exist_ok=True)
    path = owner_dir / f"{file_id}.source{ext}"
    path.write_bytes(raw)
    return file_id


async def ensure_motion_outline_ready(owner_id: int, file_id: str) -> None:
    """Если outline ещё не готов — обработать синхронно в worker (fallback)."""
    import anyio

    if resolve_motion_video_file(owner_id, file_id) is not None:
        return
    source = resolve_motion_video_source(owner_id, file_id)
    if source is None:
        legacy = resolve_motion_video_file(owner_id, file_id)
        if legacy is not None:
            return
        raise RuntimeError("Референс-видео не найдено. Загрузите файл снова.")
    result = await anyio.to_thread.run_sync(process_motion_video_outline, source)
    try:
        publish_outline_for_owner(owner_id=owner_id, file_id=file_id, outline=result.outline_path)
    finally:
        result.outline_path.unlink(missing_ok=True)


def publish_outline_for_owner(
    *,
    owner_id: int,
    file_id: str,
    outline: Path,
) -> str:
    """Копирует outline как `{file_id}.mp4` для публичного URL."""
    from app.services.studio_motion_video import MOTION_VIDEO_ROOT

    owner_dir = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    root = MOTION_VIDEO_ROOT.resolve()
    if not str(owner_dir).startswith(str(root)):
        raise RuntimeError("invalid motion video path")
    owner_dir.mkdir(parents=True, exist_ok=True)
    dest = owner_dir / f"{file_id.strip()[:128]}.mp4"
    shutil.copy2(outline, dest)
    return file_id
