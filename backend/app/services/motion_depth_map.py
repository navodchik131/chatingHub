"""Grayscale depth-map video из motion-референса (control signal для Seedance T2V)."""

from __future__ import annotations

import logging
import subprocess
import urllib.request
from pathlib import Path
from typing import Iterator

import numpy as np

from app.config import BACKEND_DIR
from app.services.motion_video_outline import _ffmpeg_bin, _ffprobe_bin, _run_cmd, probe_motion_video_stream

log = logging.getLogger(__name__)

MIDAS_DIR = (BACKEND_DIR / "data" / "models" / "midas").resolve()
MIDAS_MODEL = MIDAS_DIR / "midas_v21_small_256.onnx"
MIDAS_URL = "https://github.com/isl-org/MiDaS/releases/download/v2_1/midas_v21_small_256.onnx"

_MIDAS_SESSION: object | None = None


def _ensure_midas_model() -> Path:
    if MIDAS_MODEL.is_file() and MIDAS_MODEL.stat().st_size > 100_000:
        return MIDAS_MODEL
    MIDAS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MIDAS_MODEL.with_suffix(".onnx.part")
    log.info("motion depth map: downloading MiDaS model")
    try:
        urllib.request.urlretrieve(MIDAS_URL, tmp)  # noqa: S310
        if tmp.stat().st_size < 100_000:
            raise RuntimeError("MiDaS download looks truncated")
        tmp.replace(MIDAS_MODEL)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return MIDAS_MODEL


def _get_midas_session():
    global _MIDAS_SESSION
    if _MIDAS_SESSION is not None:
        return _MIDAS_SESSION
    import onnxruntime as ort

    model = _ensure_midas_model()
    _MIDAS_SESSION = ort.InferenceSession(
        str(model),
        providers=["CPUExecutionProvider"],
    )
    return _MIDAS_SESSION


def _probe_fps(path: Path) -> float:
    r = _run_cmd(
        [
            _ffprobe_bin(),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate,avg_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        timeout=30,
    )
    if r.returncode != 0:
        return 30.0
    for raw in [ln.strip() for ln in str(r.stdout or "").splitlines() if ln.strip()]:
        if "/" in raw:
            num, den = raw.split("/", 1)
            try:
                n, d = float(num), float(den)
                if d > 0 and n > 0:
                    fps = n / d
                    if 5 <= fps <= 120:
                        return fps
            except ValueError:
                continue
        else:
            try:
                fps = float(raw)
                if 5 <= fps <= 120:
                    return fps
            except ValueError:
                continue
    return 30.0


def _frame_to_depth_bgr(frame_bgr: np.ndarray, session) -> np.ndarray:
    """Белый = ближе, чёрный = дальше; гладкие поверхности без текстуры."""
    import cv2

    h, w = frame_bgr.shape[:2]
    inp = cv2.resize(frame_bgr, (256, 256), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(inp, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    rgb = (rgb - 0.5) / 0.5
    blob = rgb.transpose(2, 0, 1)[None, ...]
    input_name = session.get_inputs()[0].name
    depth = session.run(None, {input_name: blob})[0]
    depth = np.squeeze(depth).astype(np.float32)
    depth = cv2.resize(depth, (w, h), interpolation=cv2.INTER_CUBIC)
    dmin, dmax = float(depth.min()), float(depth.max())
    if dmax > dmin:
        norm = (depth - dmin) / (dmax - dmin)
    else:
        norm = np.zeros_like(depth)
    # MiDaS: больше значение ≈ ближе → белый
    gray = (norm * 255.0).astype(np.uint8)
    gray = cv2.GaussianBlur(gray, (9, 9), 0)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _fallback_depth_bgr(frame_bgr: np.ndarray) -> np.ndarray:
    """Запасной control-signal без MiDaS — distance transform + blur."""
    import cv2

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    edges = cv2.Canny(gray, 40, 120)
    inv = cv2.bitwise_not(edges)
    dist = cv2.distanceTransform(inv, cv2.DIST_L2, 5)
    dist = cv2.normalize(dist, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    dist = cv2.GaussianBlur(dist, (15, 15), 0)
    return cv2.cvtColor(dist, cv2.COLOR_GRAY2BGR)


def _iter_frames_bgr(source: Path) -> tuple[float, int, int, Iterator[np.ndarray]]:
    w, h, _dur = probe_motion_video_stream(source)
    fps = _probe_fps(source)
    frame_size = w * h * 3
    cmd = [
        _ffmpeg_bin(),
        "-v",
        "error",
        "-i",
        str(source),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def gen() -> Iterator[np.ndarray]:
        assert proc.stdout is not None
        try:
            while True:
                raw = proc.stdout.read(frame_size)
                if not raw or len(raw) < frame_size:
                    break
                yield np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3)).copy()
        finally:
            proc.stdout.close()
            proc.wait(timeout=5)

    return fps, w, h, gen()


def _encode_depth_video(
    dest: Path,
    *,
    fps: float,
    width: int,
    height: int,
    frames: Iterator[np.ndarray],
    timeout: float,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    cmd = [
        _ffmpeg_bin(),
        "-v",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.3f}",
        "-i",
        "-",
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
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for frame in frames:
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        err = proc.stderr.read() if proc.stderr else b""
        rc = proc.wait(timeout=timeout)
        if rc != 0:
            raise RuntimeError(f"depth ffmpeg encode failed: {err.decode('utf-8', errors='replace')[:800]}")
    except Exception:
        proc.kill()
        dest.unlink(missing_ok=True)
        raise


def render_motion_depth_map_video(source: Path, dest: Path, *, timeout: float = 600.0) -> None:
    """Покадровая depth-map: white=near, black=far, без текстуры."""
    fps, w, h, frame_iter = _iter_frames_bgr(source)
    session = None
    try:
        session = _get_midas_session()
    except Exception as e:
        log.warning("motion depth map: MiDaS unavailable (%s), fallback depth", e)

    def processed() -> Iterator[np.ndarray]:
        for frame in frame_iter:
            if session is not None:
                try:
                    yield _frame_to_depth_bgr(frame, session)
                    continue
                except Exception:
                    log.warning("motion depth map: MiDaS frame failed, fallback", exc_info=True)
            yield _fallback_depth_bgr(frame)

    _encode_depth_video(dest, fps=fps, width=w, height=h, frames=processed(), timeout=timeout)


def motion_depth_video_path(owner_id: int, file_id: str) -> Path:
    from app.services.studio_motion_video import MOTION_VIDEO_ROOT

    base = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    fid = str(file_id).strip()[:128]
    return base / f"{fid}.depth.mp4"


def ensure_motion_depth_map_video(owner_id: int, file_id: str, source: Path, *, timeout: float = 600.0) -> Path:
    """Кеш depth-map рядом с реф-видео; пересчёт если исходник новее."""
    dest = motion_depth_video_path(owner_id, file_id)
    if dest.is_file() and dest.stat().st_size > 1024:
        if dest.stat().st_mtime >= source.stat().st_mtime:
            return dest
    render_motion_depth_map_video(source, dest, timeout=timeout)
    return dest
