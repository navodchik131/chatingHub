"""Силуэт только человека (rembg + контур внутри маски), фон — без изменений."""

from __future__ import annotations

import logging
import math
import os
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from app.config import BACKEND_DIR
from app.services.motion_video_outline import (
    EdgeOutlineParams,
    _ffmpeg_bin,
    _ffprobe_bin,
    _run_cmd,
    _stderr_text,
    probe_motion_video_stream,
    source_has_audio_stream,
)
from app.services.studio_motion_video import mux_original_audio_onto_video

log = logging.getLogger(__name__)

YUNET_DIR = (BACKEND_DIR / "data" / "models" / "yunet").resolve()
YUNET_MODEL = YUNET_DIR / "face_detection_yunet_2023mar.onnx"
YUNET_URL = (
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
    "models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
)

# Версия алгоритма — для cache-bust при изменениях пайплайна.
SELECTIVE_OUTLINE_ALGO = "person-v1"

_REMBG_SESSION: Any | None = None
_YUNET_DETECTOR: Any | None = None


@dataclass
class _FaceTrack:
    cx: float
    cy: float
    ax: float
    ay: float
    angle: float
    score: float
    missed: int = 0


@dataclass
class _FaceTracker:
    tracks: list[_FaceTrack] = field(default_factory=list)
    ema: float = 0.55
    max_miss: int = 6
    match_dist: float = 80.0

    def update(self, detections: list[tuple[float, float, float, float, float, float]]) -> list[_FaceTrack]:
        """detections: (cx, cy, ax, ay, angle, score)"""
        used: set[int] = set()
        for det in detections:
            cx, cy, ax, ay, angle, score = det
            best_i = -1
            best_d = self.match_dist
            for i, tr in enumerate(self.tracks):
                if i in used:
                    continue
                d = math.hypot(tr.cx - cx, tr.cy - cy)
                if d < best_d:
                    best_d = d
                    best_i = i
            if best_i >= 0:
                tr = self.tracks[best_i]
                a = self.ema
                tr.cx = a * cx + (1 - a) * tr.cx
                tr.cy = a * cy + (1 - a) * tr.cy
                tr.ax = a * ax + (1 - a) * tr.ax
                tr.ay = a * ay + (1 - a) * tr.ay
                tr.angle = a * angle + (1 - a) * tr.angle
                tr.score = max(tr.score, score)
                tr.missed = 0
                used.add(best_i)
            else:
                self.tracks.append(_FaceTrack(cx, cy, ax, ay, angle, score, missed=0))

        alive: list[_FaceTrack] = []
        for i, tr in enumerate(self.tracks):
            if i in used:
                alive.append(tr)
            elif tr.missed < self.max_miss:
                tr.missed += 1
                alive.append(tr)
        self.tracks = alive
        return list(self.tracks)


def _ensure_yunet_model() -> Path:
    if YUNET_MODEL.is_file() and YUNET_MODEL.stat().st_size > 50_000:
        return YUNET_MODEL
    YUNET_DIR.mkdir(parents=True, exist_ok=True)
    log.info("motion selective outline: downloading YuNet model")
    tmp = YUNET_MODEL.with_suffix(".onnx.part")
    try:
        urllib.request.urlretrieve(YUNET_URL, tmp)  # noqa: S310
        if tmp.stat().st_size < 50_000:
            raise RuntimeError("YuNet download looks like LFS pointer, not ONNX weights")
        tmp.replace(YUNET_MODEL)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return YUNET_MODEL


def _get_rembg_session() -> Any:
    global _REMBG_SESSION
    if _REMBG_SESSION is not None:
        return _REMBG_SESSION
    from rembg import new_session

    try:
        _REMBG_SESSION = new_session("u2net_human_seg")
    except Exception as e:
        # bad_alloc / OOM onnx — пусть сработает ffmpeg fallback в _render_outline.
        log.warning("rembg session init failed: %s", e)
        raise RuntimeError(f"rembg недоступен: {e}") from e
    return _REMBG_SESSION


def _get_yunet_detector(frame_w: int, frame_h: int) -> Any:
    import cv2

    global _YUNET_DETECTOR
    model = _ensure_yunet_model()
    if _YUNET_DETECTOR is None:
        _YUNET_DETECTOR = cv2.FaceDetectorYN.create(str(model), "", (frame_w, frame_h), 0.7, 0.3, 5000)
    else:
        _YUNET_DETECTOR.setInputSize((frame_w, frame_h))
    return _YUNET_DETECTOR


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
    lines = [ln.strip() for ln in str(r.stdout or "").splitlines() if ln.strip()]
    for raw in lines:
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


def _canny_thresholds(params: EdgeOutlineParams) -> tuple[int, int]:
    low = int(max(25, min(120, params.low * 500)))
    high = int(max(low + 20, min(220, params.high * 500)))
    return low, high


def _human_mask_bgr(frame_bgr: np.ndarray, session: Any, *, max_seg_h: int = 720) -> np.ndarray:
    """Маска человека 0/255; сегментация на уменьшенном кадре для скорости."""
    import cv2
    from rembg import remove

    h, w = frame_bgr.shape[:2]
    if h <= 0 or w <= 0:
        return np.zeros((max(1, h), max(1, w)), dtype=np.uint8)

    scale = 1.0
    if h > max_seg_h:
        scale = max_seg_h / h
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        small = cv2.resize(frame_bgr, (sw, sh), interpolation=cv2.INTER_AREA)
    else:
        small = frame_bgr

    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    from PIL import Image

    rgba = np.array(remove(Image.fromarray(rgb), session=session))
    if rgba.ndim != 3 or rgba.shape[2] < 4:
        return np.zeros((h, w), dtype=np.uint8)
    alpha = rgba[:, :, 3]
    mask_small = (alpha > 40).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_small = cv2.morphologyEx(mask_small, cv2.MORPH_CLOSE, kernel)
    mask_small = cv2.GaussianBlur(mask_small, (9, 9), 0)

    if scale != 1.0:
        mask = cv2.resize(mask_small, (w, h), interpolation=cv2.INTER_LINEAR)
    else:
        mask = mask_small
    return mask


def _detect_faces_yunet(frame_bgr: np.ndarray, detector: Any) -> list[tuple[float, float, float, float, float, float]]:
    import cv2

    h, w = frame_bgr.shape[:2]
    _, faces = detector.detect(frame_bgr)
    out: list[tuple[float, float, float, float, float, float]] = []
    if faces is None:
        return out
    for face in faces:
        if len(face) < 15:
            continue
        score = float(face[14])
        if score < 0.65:
            continue
        x, y, fw, fh = float(face[0]), float(face[1]), float(face[2]), float(face[3])
        rx, ry = float(face[4]), float(face[5])
        lx, ly = float(face[6]), float(face[7])
        angle = math.degrees(math.atan2(ly - ry, lx - rx))
        cx = x + fw * 0.5
        cy = y + fh * 0.45
        ax = max(fw * 0.55, 12.0)
        ay = max(fh * 0.65, 14.0)
        out.append((cx, cy, ax, ay, angle, score))
    return out


def _draw_rotated_ellipse_mask(shape: tuple[int, int], track: _FaceTrack) -> np.ndarray:
    import cv2

    h, w = shape
    mask = np.zeros((h, w), dtype=np.uint8)
    center = (int(round(track.cx)), int(round(track.cy)))
    axes = (int(round(track.ax)), int(round(track.ay)))
    cv2.ellipse(mask, center, axes, track.angle, 0, 360, 255, -1)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)
    return mask


def _edges_in_region(gray: np.ndarray, region_mask: np.ndarray, params: EdgeOutlineParams, *, upscale: float) -> np.ndarray:
    import cv2

    low, high = _canny_thresholds(params)
    ys, xs = np.where(region_mask > 32)
    if len(xs) == 0:
        return np.zeros_like(gray)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    pad = 8
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(gray.shape[1] - 1, x1 + pad)
    y1 = min(gray.shape[0] - 1, y1 + pad)
    crop = gray[y0 : y1 + 1, x0 : x1 + 1]
    m_crop = region_mask[y0 : y1 + 1, x0 : x1 + 1]
    if crop.size == 0:
        return np.zeros_like(gray)

    if upscale > 1.01:
        crop_up = cv2.resize(crop, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
        m_up = cv2.resize(m_crop, (crop_up.shape[1], crop_up.shape[0]), interpolation=cv2.INTER_LINEAR)
    else:
        crop_up = crop
        m_up = m_crop

    blur = cv2.GaussianBlur(crop_up, (5, 5), 0)
    edges_up = cv2.Canny(blur, low, high)
    edges_up[m_up <= 32] = 0
    if upscale > 1.01:
        edges_crop = cv2.resize(edges_up, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_AREA)
    else:
        edges_crop = edges_up

    out = np.zeros_like(gray)
    out[y0 : y1 + 1, x0 : x1 + 1] = edges_crop
    return out


def _compose_person_outline_frame(
    frame_bgr: np.ndarray,
    *,
    person_mask: np.ndarray,
    body_edges: np.ndarray,
    face_edges: np.ndarray | None,
) -> np.ndarray:
    import cv2

    h, w = frame_bgr.shape[:2]
    mask = cv2.GaussianBlur(person_mask, (5, 5), 0).astype(np.float32) / 255.0
    edges = body_edges.copy()
    if face_edges is not None:
        edges = np.maximum(edges, face_edges)

    inside = np.full((h, w, 3), 255, dtype=np.uint8)
    inside[edges > 0] = (0, 0, 0)

    mask_3 = np.stack([mask, mask, mask], axis=-1)
    out = (frame_bgr.astype(np.float32) * (1.0 - mask_3) + inside.astype(np.float32) * mask_3).astype(np.uint8)
    return out


def _process_frame_person_outline(
    frame_bgr: np.ndarray,
    *,
    rembg_session: Any,
    params: EdgeOutlineParams,
    tracker: _FaceTracker,
    yunet: Any | None,
) -> np.ndarray:
    import cv2

    person_mask = _human_mask_bgr(frame_bgr, rembg_session)
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    body_edges = _edges_in_region(gray, person_mask, params, upscale=1.0)

    face_edges: np.ndarray | None = None
    if yunet is not None:
        dets = _detect_faces_yunet(frame_bgr, yunet)
        tracks = tracker.update(dets)
        if tracks:
            face_edges = np.zeros_like(gray)
            for tr in tracks:
                fmask = _draw_rotated_ellipse_mask(gray.shape, tr)
                fmask = cv2.bitwise_and(fmask, person_mask)
                fe = _edges_in_region(gray, fmask, params, upscale=2.5)
                face_edges = np.maximum(face_edges, fe)

    return _compose_person_outline_frame(
        frame_bgr,
        person_mask=person_mask,
        body_edges=body_edges,
        face_edges=face_edges,
    )


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


def _encode_frames_bgr(
    dest: Path,
    *,
    fps: float,
    width: int,
    height: int,
    frames: Iterator[np.ndarray],
    out_w: int,
    out_h: int,
    timeout: float,
) -> None:
    import cv2

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
        f"{out_w}x{out_h}",
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
            if (frame.shape[1], frame.shape[0]) != (width, height):
                raise RuntimeError("Размер кадра видео изменился во время обработки.")
            if out_w != width or out_h != height:
                frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA)
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        err = proc.stderr.read() if proc.stderr else b""
        rc = proc.wait(timeout=timeout)
        if rc != 0:
            raise RuntimeError(f"ffmpeg encode failed: {err.decode('utf-8', errors='replace')[:800]}")
    except Exception:
        proc.kill()
        dest.unlink(missing_ok=True)
        raise


def render_person_selective_outline(source: Path, dest: Path, params: EdgeOutlineParams, *, timeout: float) -> None:
    """Покадровый силуэт человека: rembg-маска + контур внутри, фон — оригинал."""
    fps, w, h, frame_iter = _iter_frames_bgr(source)
    rembg_session = _get_rembg_session()
    tracker = _FaceTracker()
    yunet: Any | None = None
    try:
        yunet = _get_yunet_detector(w, h)
    except Exception as e:
        log.warning("motion selective outline: YuNet unavailable (%s), body-only edges", e)

    def processed() -> Iterator[np.ndarray]:
        for frame in frame_iter:
            yield _process_frame_person_outline(
                frame,
                rembg_session=rembg_session,
                params=params,
                tracker=tracker,
                yunet=yunet,
            )

    _encode_frames_bgr(
        dest,
        fps=fps,
        width=w,
        height=h,
        frames=processed(),
        out_w=params.out_w,
        out_h=params.out_h,
        timeout=timeout,
    )

    if source_has_audio_stream(source):
        if not mux_original_audio_onto_video(dest, source):
            log.warning("motion selective outline: failed to mux audio onto %s", dest.name)


def selective_outline_cache_tag() -> str:
    return SELECTIVE_OUTLINE_ALGO
