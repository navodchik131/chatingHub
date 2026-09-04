"""Grayscale depth-map video из motion-референса (control signal для Seedance T2V)."""

from __future__ import annotations

import logging
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from app.config import BACKEND_DIR
from app.services.motion_video_outline import _ffmpeg_bin, _ffprobe_bin, _run_cmd, probe_motion_video_stream

log = logging.getLogger(__name__)

# v3: полная сцена MiDaS + rembg усиливает силуэт человека (фон не чёрный).
DEPTH_MAP_ALGO = "v3"
MIDAS_DIR = (BACKEND_DIR / "data" / "models" / "midas").resolve()
# В релизе v2_1 файл называется model-small.onnx (midas_v21_small_256.onnx — 404).
MIDAS_MODEL = MIDAS_DIR / "model-small.onnx"
MIDAS_URL = "https://github.com/isl-org/MiDaS/releases/download/v2_1/model-small.onnx"
MIDAS_INPUT_SIZE = 256

_MIDAS_SESSION: object | None = None


def _ensure_midas_model() -> Path:
    if MIDAS_MODEL.is_file() and MIDAS_MODEL.stat().st_size > 100_000:
        return MIDAS_MODEL
    MIDAS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MIDAS_MODEL.with_suffix(".onnx.part")
    log.info("motion depth map: downloading MiDaS model-small.onnx")
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


def _get_rembg_session_safe() -> Any | None:
    """rembg для усиления силуэта человека; при OOM — depth только по MiDaS."""
    try:
        from app.services.motion_selective_outline import _get_rembg_session

        return _get_rembg_session()
    except Exception as e:
        log.warning("motion depth map: rembg unavailable (%s), depth without person mask", e)
        return None


def _human_mask_bgr_safe(frame_bgr: np.ndarray, rembg_session: Any | None) -> np.ndarray | None:
    if rembg_session is None:
        return None
    try:
        from app.services.motion_selective_outline import _human_mask_bgr

        return _human_mask_bgr(frame_bgr, rembg_session)
    except Exception as e:
        log.warning("motion depth map: rembg frame failed (%s)", e)
        return None


def _percentile_norm01(values: np.ndarray, *, lo_pct: float, hi_pct: float) -> np.ndarray:
    lo = float(np.percentile(values, lo_pct))
    hi = float(np.percentile(values, hi_pct))
    if hi <= lo:
        hi = lo + 1e-6
    return np.clip((values - lo) / (hi - lo), 0.0, 1.0)


def _soft_person_alpha(fg_mask: np.ndarray) -> np.ndarray:
    """Мягкая маска 0..1 для плавного перехода человек ↔ окружение."""
    import cv2

    m = (fg_mask > 127).astype(np.float32)
    if not np.any(m > 0.01):
        return m
    return cv2.GaussianBlur(m, (21, 21), 0)


def _compose_scene_depth_gray(depth: np.ndarray, *, fg_mask: np.ndarray | None) -> np.ndarray:
    """
    Белый = ближе, чёрный = дальше.
    Окружение и предметы видны (глобальная нормализация MiDaS).
    Человек ярче и контрастнее фона — rembg-маска усиливает локальную глубину тела.
    """
    import cv2

    d = depth.astype(np.float32)
    # Слой сцены: стены, пол, реквизит — всё остаётся читаемым.
    scene01 = _percentile_norm01(d, lo_pct=2, hi_pct=98)
    scene_gray = (scene01 * 255.0).astype(np.float32)

    if fg_mask is None or not np.any(fg_mask > 127):
        gray = scene_gray
    else:
        fg = fg_mask > 127
        person01 = _percentile_norm01(d[fg], lo_pct=4, hi_pct=96)
        person_full = np.zeros_like(d, dtype=np.float32)
        person_full[fg] = person01
        # Человек: широкий диапазон 48–255; окружение приглушено (~62% яркости).
        person_gray = 48.0 + person_full * 207.0
        scene_layer = scene_gray * 0.62
        alpha = _soft_person_alpha(fg_mask)
        gray = alpha * person_gray + (1.0 - alpha) * scene_layer

    out = np.clip(gray, 0, 255).astype(np.uint8)
    out = cv2.bilateralFilter(out, 7, 40, 40)
    return out


def _normalize_depth_to_gray(depth: np.ndarray, *, fg_mask: np.ndarray | None) -> np.ndarray:
    """Обратная совместимость для тестов."""
    return _compose_scene_depth_gray(depth, fg_mask=fg_mask)


def _run_midas_depth(frame_bgr: np.ndarray, session) -> np.ndarray:
    """Сырой depth map MiDaS, размер как у кадра."""
    import cv2

    h, w = frame_bgr.shape[:2]
    inp = cv2.resize(frame_bgr, (MIDAS_INPUT_SIZE, MIDAS_INPUT_SIZE), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(inp, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    rgb = (rgb - 0.5) / 0.5
    blob = rgb.transpose(2, 0, 1)[None, ...]
    input_name = session.get_inputs()[0].name
    depth = session.run(None, {input_name: blob})[0]
    depth = np.squeeze(depth).astype(np.float32)
    return cv2.resize(depth, (w, h), interpolation=cv2.INTER_CUBIC)


def _frame_to_depth_bgr(
    frame_bgr: np.ndarray,
    session,
    *,
    rembg_session: Any | None = None,
) -> np.ndarray:
    """MiDaS depth: сцена + предметы + усиленный силуэт человека."""
    import cv2

    mask = _human_mask_bgr_safe(frame_bgr, rembg_session)
    depth = _run_midas_depth(frame_bgr, session)
    gray = _compose_scene_depth_gray(depth, fg_mask=mask)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _fallback_depth_bgr(frame_bgr: np.ndarray, *, rembg_session: Any | None = None) -> np.ndarray:
    """
    Запасной control-signal без MiDaS: яркость кадра как грубая глубина сцены
    + rembg pseudo-depth для усиления человека.
    """
    import cv2

    mask = _human_mask_bgr_safe(frame_bgr, rembg_session)
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray = cv2.GaussianBlur(gray, (7, 7), 0)
    scene_depth = gray.copy()

    if mask is not None and np.any(mask > 127):
        fg = (mask > 127).astype(np.uint8)
        dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
        if float(dist.max()) > 1e-3:
            dist = dist / float(dist.max())
        person_depth = dist * 255.0
        # Смешиваем псевдо-глубину человека с яркостью сцены.
        blend_src = np.maximum(scene_depth, person_depth)
        gray = _compose_scene_depth_gray(blend_src, fg_mask=mask)
    else:
        gray = _compose_scene_depth_gray(scene_depth, fg_mask=None)

    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


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
        "18",
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
    """Покадровая depth-map: white=near, black=far; человек контрастнее окружения."""
    fps, w, h, frame_iter = _iter_frames_bgr(source)
    session = None
    rembg_session = _get_rembg_session_safe()
    try:
        session = _get_midas_session()
        log.info("motion depth map: MiDaS model-small ready algo=%s", DEPTH_MAP_ALGO)
    except Exception as e:
        log.error("motion depth map: MiDaS unavailable (%s), using rembg fallback depth", e)

    used_midas = session is not None
    frame_idx = 0

    def processed() -> Iterator[np.ndarray]:
        nonlocal frame_idx
        for frame in frame_iter:
            frame_idx += 1
            if session is not None:
                try:
                    yield _frame_to_depth_bgr(frame, session, rembg_session=rembg_session)
                    continue
                except Exception:
                    log.warning(
                        "motion depth map: MiDaS frame %s failed, fallback",
                        frame_idx,
                        exc_info=True,
                    )
            yield _fallback_depth_bgr(frame, rembg_session=rembg_session)

    _encode_depth_video(dest, fps=fps, width=w, height=h, frames=processed(), timeout=timeout)
    if not used_midas:
        log.warning(
            "motion depth map: rendered WITHOUT MiDaS (%s frames) — проверьте model-small.onnx",
            frame_idx,
        )


def motion_depth_video_path(owner_id: int, file_id: str) -> Path:
    from app.services.studio_motion_video import MOTION_VIDEO_ROOT

    base = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    fid = str(file_id).strip()[:128]
    return base / f"{fid}.depth.{DEPTH_MAP_ALGO}.mp4"


def ensure_motion_depth_map_video(owner_id: int, file_id: str, source: Path, *, timeout: float = 600.0) -> Path:
    """Кеш depth-map рядом с реф-видео; пересчёт если исходник новее."""
    dest = motion_depth_video_path(owner_id, file_id)
    if dest.is_file() and dest.stat().st_size > 1024:
        if dest.stat().st_mtime >= source.stat().st_mtime:
            return dest
    render_motion_depth_map_video(source, dest, timeout=timeout)
    return dest
