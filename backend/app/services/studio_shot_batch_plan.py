from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.motion_video_outline import _detect_face_in_jpeg
from app.services.studio_motion_video import _ffmpeg_bin, probe_video_duration_seconds


@dataclass(frozen=True)
class ShotPlan:
    id: int
    t_start: float
    t_end: float
    duration: float
    subject_visibility_status: str  # visible|uncertain|not_detected
    difficulty: str  # low|medium|high
    face_hits: int
    object_risk_level: str  # low|medium|high
    motion_score: float


@dataclass(frozen=True)
class BatchPlan:
    id: int
    shot_ids: list[int]
    t_start: float
    t_end: float
    duration: float
    has_subject: bool
    identity_anchor_visible: bool  # first shot in batch has subject_visible
    object_risk_level: str  # low|medium|high
    risky: bool
    risky_reason: str | None


def _ffprobe_duration(path: Path) -> float | None:
    try:
        return probe_video_duration_seconds(path)
    except Exception:
        return None


def _probe_scene_cut_times(
    video_path: Path,
    *,
    scene_threshold: float,
) -> list[float]:
    """
    Return sorted cut timestamps in seconds (excluding 0 and duration).

    Uses ffmpeg `select='gt(scene,THR)',showinfo'`.
    """
    th = float(scene_threshold)
    if not math.isfinite(th) or th <= 0:
        th = 0.35

    # ffmpeg prints showinfo to stderr; collect pts_time values.
    cmd = [
        _ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        str(video_path),
        "-filter:v",
        f"select='gt(scene\\,{th})',showinfo",
        "-vsync",
        "vfr",
        "-f",
        "null",
        "-",
    ]
    r = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=600)
    text = (r.stderr or "") + "\n" + (r.stdout or "")

    # showinfo usually contains: "pts_time:12.345" or "pts_time=12.345"
    hits = re.findall(r"pts_time[:=]([0-9]*\\.?[0-9]+)", text)
    times: list[float] = []
    for h in hits:
        try:
            t = float(h)
        except Exception:
            continue
        if t > 1e-3:
            times.append(t)
    times = sorted(set(times))
    return times


def _extract_jpeg_frame_bytes(
    video_path: Path,
    *,
    t: float,
    jpeg_quality: int = 5,
) -> bytes | None:
    t2 = max(0.0, float(t))
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "frame.jpg"
        cmd = [
            _ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{t2:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            str(jpeg_quality),
            str(out),
        ]
        rr = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=60)
        if rr.returncode != 0:
            return None
        if not out.is_file() or out.stat().st_size < 64:
            return None
        return out.read_bytes()


def _subject_visible_in_shot(
    video_path: Path,
    *,
    t_start: float,
    t_end: float,
    face_samples: int,
) -> tuple[int, bool]:
    dur = max(0.0, float(t_end) - float(t_start))
    if dur <= 0.05:
        t_samples = [t_start]
    else:
        n = max(1, int(face_samples))
        t_samples = [
            t_start + (dur * i) / max(1, n - 1)
            for i in range(n)
        ]

    hits = 0
    for t in t_samples:
        frame = _extract_jpeg_frame_bytes(video_path, t=t)
        if not frame:
            continue
        if _detect_face_in_jpeg(frame):
            hits += 1
    return hits, hits > 0


def _motion_score_in_shot(
    video_path: Path,
    *,
    t_start: float,
    t_end: float,
    samples: int,
) -> float:
    """
    Cheap heuristic: mean absolute difference of consecutive grayscale frames.
    If cv2 isn't available, returns 0.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return 0.0

    dur = max(0.0, float(t_end) - float(t_start))
    if dur <= 0.05:
        return 0.0

    n = max(2, int(samples))
    t_samples = [t_start + (dur * i) / (n - 1) for i in range(n)]
    frames: list[Any] = []
    for t in t_samples:
        frame = _extract_jpeg_frame_bytes(video_path, t=t, jpeg_quality=8)
        if not frame:
            continue
        arr = np.frombuffer(frame, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        frames.append(img)
    if len(frames) < 2:
        return 0.0

    total = 0.0
    count = 0
    for a, b in zip(frames, frames[1:]):
        if a.shape != b.shape:
            b = cv2.resize(b, (a.shape[1], a.shape[0]))
        diff = cv2.absdiff(a, b)
        total += float(diff.mean())
        count += 1
    return total / max(1, count)


def _difficulty_from_heuristics(
    *,
    subject_visibility_status: str,
    shot_dur: float,
    motion_score: float,
    object_risk_level: str,
) -> str:
    if subject_visibility_status == "not_detected":
        return "low"
    if object_risk_level == "high":
        return "high"
    # Rough heuristic: longer + more motion => high.
    if shot_dur >= 2.2 or motion_score >= 14.0:
        return "high"
    if shot_dur >= 1.2 or motion_score >= 8.0:
        return "medium"
    return "low"


def _object_risk_from_motion(motion_score: float) -> str:
    if motion_score >= 18.0:
        return "high"
    if motion_score >= 12.0:
        return "medium"
    return "low"


def _subject_status_from_face_and_motion(
    *,
    face_hits: int,
    face_detected: bool,
    shot_dur: float,
    motion_score: float,
) -> str:
    if face_detected:
        return "visible"
    # No face detected, but if the shot is long/dynamic we treat it as "uncertain"
    # (this matches your real-world case where the subject is turned back).
    if shot_dur >= 1.1 or motion_score >= 10.0:
        return "uncertain"
    return "not_detected"


def plan_shot_batches(
    video_path: Path,
    *,
    scene_threshold: float = 0.35,
    max_shots_per_batch: int = 4,
    max_batch_duration_sec: float = 12.0,
    min_shot_duration_sec: float = 0.4,
    face_samples: int = 6,
) -> dict[str, Any]:
    duration = _ffprobe_duration(video_path)
    if duration is None or duration <= 0.1:
        raise RuntimeError("Не удалось определить длительность видео для shot-batch plan.")

    cut_times = _probe_scene_cut_times(video_path, scene_threshold=scene_threshold)
    # Build raw shots from 0 -> duration with cuts in between.
    all_points = [0.0] + [t for t in cut_times if 0 < t < duration] + [duration]
    all_points = sorted(all_points)

    shots_raw: list[tuple[float, float]] = []
    for a, b in zip(all_points, all_points[1:]):
        t0, t1 = float(a), float(b)
        if t1 - t0 < min_shot_duration_sec:
            continue
        shots_raw.append((t0, t1))
    if not shots_raw:
        shots_raw = [(0.0, duration)]

    shots: list[ShotPlan] = []
    for idx, (t0, t1) in enumerate(shots_raw, start=1):
        face_hits, face_detected = _subject_visible_in_shot(
            video_path,
            t_start=t0,
            t_end=t1,
            face_samples=face_samples,
        )
        motion_score = _motion_score_in_shot(
            video_path,
            t_start=t0,
            t_end=t1,
            samples=min(6, max(2, face_samples)),
        )
        object_risk_level = _object_risk_from_motion(motion_score)
        subject_status = _subject_status_from_face_and_motion(
            face_hits=face_hits,
            face_detected=face_detected,
            shot_dur=t1 - t0,
            motion_score=motion_score,
        )
        difficulty = _difficulty_from_heuristics(
            subject_visibility_status=subject_status,
            shot_dur=t1 - t0,
            motion_score=motion_score,
            object_risk_level=object_risk_level,
        )
        shots.append(
            ShotPlan(
                id=idx,
                t_start=t0,
                t_end=t1,
                duration=t1 - t0,
                subject_visibility_status=subject_status,
                difficulty=difficulty,
                face_hits=face_hits,
                object_risk_level=object_risk_level,
                motion_score=motion_score,
            )
        )

    # Batch selection (greedy).
    batches: list[BatchPlan] = []
    cur: list[ShotPlan] = []
    cur_dur = 0.0

    def _flush() -> None:
        nonlocal cur, cur_dur
        if not cur:
            return
        shot_ids = [s.id for s in cur]
        t_start = cur[0].t_start
        t_end = cur[-1].t_end
        has_subject = any(s.subject_visibility_status != "not_detected" for s in cur)
        anchor_visible = bool(cur[0].subject_visibility_status == "visible")
        risk_order = {"low": 0, "medium": 1, "high": 2}
        object_risk_level = max((s.object_risk_level for s in cur), key=lambda x: risk_order.get(x, 0))
        risky = False
        risky_reason = None
        if has_subject and not anchor_visible:
            risky = True
            risky_reason = "identity_anchor_visible=false (first shot has no face)"
        if not has_subject:
            # No-subject batches will be rendered without identity refs later.
            risky = False
            risky_reason = None

        batches.append(
            BatchPlan(
                id=len(batches) + 1,
                shot_ids=shot_ids,
                t_start=t_start,
                t_end=t_end,
                duration=t_end - t_start,
                has_subject=has_subject,
                identity_anchor_visible=anchor_visible,
                object_risk_level=object_risk_level,
                risky=risky,
                risky_reason=risky_reason,
            )
        )
        cur = []
        cur_dur = 0.0

    for s in shots:
        if not cur:
            cur = [s]
            cur_dur = s.duration
            continue

        # high difficulty shots start their own batch
        if s.difficulty == "high" and cur:
            _flush()
            cur = [s]
            cur_dur = s.duration
            continue

        can_add = (
            len(cur) < max_shots_per_batch
            and (cur_dur + s.duration) <= max_batch_duration_sec
        )
        if can_add:
            cur.append(s)
            cur_dur += s.duration
        else:
            _flush()
            cur = [s]
            cur_dur = s.duration

    _flush()

    return {
        "video_duration_sec": duration,
        "params": {
            "scene_threshold": scene_threshold,
            "max_shots_per_batch": max_shots_per_batch,
            "max_batch_duration_sec": max_batch_duration_sec,
            "min_shot_duration_sec": min_shot_duration_sec,
            "face_samples": face_samples,
        },
        "shots": [
            {
                "id": s.id,
                "t_start": s.t_start,
                "t_end": s.t_end,
                "duration": s.duration,
                "subject_visibility_status": s.subject_visibility_status,
                "difficulty": s.difficulty,
                "face_hits": s.face_hits,
                "object_risk_level": s.object_risk_level,
                "motion_score": s.motion_score,
            }
            for s in shots
        ],
        "batches": [
            {
                "id": b.id,
                "shot_ids": b.shot_ids,
                "t_start": b.t_start,
                "t_end": b.t_end,
                "duration": b.duration,
                "has_subject": b.has_subject,
                "identity_anchor_visible": b.identity_anchor_visible,
                "object_risk_level": b.object_risk_level,
                "risky": b.risky,
                "risky_reason": b.risky_reason,
            }
            for b in batches
        ],
    }

