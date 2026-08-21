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


@dataclass(frozen=True)
class ResolvedBatchPlan:
    id: int
    source_batch_id: int
    shot_ids: list[int]
    effective_shot_ids: list[int]
    effective_t_start: float
    effective_t_end: float
    effective_duration: float
    resolution_action: str  # native_first_shot|shift_boundary_forward|synthetic_opening_frame|manual_review
    requires_synthetic_opening_frame: bool
    manual_review_required: bool
    reason: str
    identity_string_policy: str
    object_risk_level: str


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
    # Absolute motion alone is NOT enough for "high": continuous body/camera
    # rotation has high MAD everywhere and must not explode into 1-shot batches.
    if object_risk_level == "high" and motion_score >= 28.0:
        return "high"
    if shot_dur >= 3.5 and motion_score >= 22.0:
        return "high"
    if shot_dur >= 2.2 or motion_score >= 14.0 or object_risk_level == "high":
        return "medium"
    if shot_dur >= 1.2 or motion_score >= 8.0:
        return "medium"
    return "low"


def _object_risk_from_motion(motion_score: float) -> str:
    # Raised thresholds: ordinary turn-in-place / pan often sits ~20–30 MAD.
    # Reserve "high" for abrupt local spikes that deserve isolation.
    if motion_score >= 34.0:
        return "high"
    if motion_score >= 22.0:
        return "medium"
    return "low"


def _should_start_new_batch_for_difficulty(cur: list[ShotPlan], nxt: ShotPlan) -> bool:
    """
    Isolate difficulty *transitions*, not continuous high-motion runs.

    A 9s rotate with no scene cuts used to become six ~1.5s high shots, each
    flushed alone → Seedance min 4s × 6 = 24s billed for ~9s of source.
    """
    if not cur:
        return False
    cur_all_high = all(x.difficulty == "high" for x in cur)
    cur_has_non_high = any(x.difficulty != "high" for x in cur)
    if nxt.difficulty == "high" and cur_has_non_high:
        return True
    if nxt.difficulty != "high" and cur_all_high:
        return True
    return False


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


def _resolve_batches(
    batches: list[BatchPlan],
    shots: list[ShotPlan],
) -> list[ResolvedBatchPlan]:
    by_id = {s.id: s for s in shots}
    out: list[ResolvedBatchPlan] = []
    for b in batches:
        members = [by_id[i] for i in b.shot_ids if i in by_id]
        if not members:
            continue

        first = members[0]
        visible_idx: int | None = None
        uncertain_idx: int | None = None
        for idx, s in enumerate(members):
            if s.subject_visibility_status == "visible":
                visible_idx = idx
                break
            if uncertain_idx is None and s.subject_visibility_status == "uncertain":
                uncertain_idx = idx

        effective_members = members
        action = "native_first_shot"
        manual_review_required = False
        requires_synth = False
        reason = "first shot is a valid identity anchor"

        if first.subject_visibility_status == "visible":
            action = "native_first_shot"
            reason = "first shot already contains a visible face anchor"
        elif visible_idx is not None and visible_idx > 0:
            effective_members = members[visible_idx:]
            action = "shift_boundary_forward"
            reason = "shift batch start to the first visible face anchor shot"
        elif uncertain_idx is not None:
            # We never got a robust visible face, but the batch likely contains the subject.
            # This is the branch for synthetic opening frame from later motion/context.
            action = "synthetic_opening_frame"
            requires_synth = True
            reason = "no visible face anchor; batch still appears to contain the subject"
        else:
            action = "manual_review"
            manual_review_required = True
            reason = "no usable subject anchor detected in any shot of the batch"

        eff_start = effective_members[0].t_start
        eff_end = effective_members[-1].t_end
        out.append(
            ResolvedBatchPlan(
                id=len(out) + 1,
                source_batch_id=b.id,
                shot_ids=list(b.shot_ids),
                effective_shot_ids=[s.id for s in effective_members],
                effective_t_start=eff_start,
                effective_t_end=eff_end,
                effective_duration=eff_end - eff_start,
                resolution_action=action,
                requires_synthetic_opening_frame=requires_synth,
                manual_review_required=manual_review_required,
                reason=reason,
                identity_string_policy="immutable_job_level_string",
                object_risk_level=b.object_risk_level,
            )
        )
    return out


def _chunk_time_span(
    t0: float,
    t1: float,
    *,
    target_len: float,
    min_shot_duration_sec: float,
    min_keep_alone_sec: float = 2.0,
) -> list[tuple[float, float]]:
    """
    Split a continuous span into regenerable chunks near target_len.

    Example: 8s + target 4 → [(0,4), (4,8)]. Short leftovers stay one chunk
    when span is only slightly above target (avoids 5s → two ~2.5s pads).
    """
    start = float(t0)
    end = float(t1)
    span = end - start
    if span < float(min_shot_duration_sec):
        return []
    # Align with Seedance duration_min so each batch maps ~1:1 to billed seconds.
    target = max(4.0, float(target_len))
    # Only force-split when we can make at least ~2 full regenerable units
    # (e.g. 8s → 2×4). A 5–7s clip stays one batch to avoid 2×4 billing.
    if span < (2.0 * target) - 0.25:
        return [(start, end)]

    n = max(2, int(round(span / target)))
    while n > 1 and (span / n) < float(min_keep_alone_sec):
        n -= 1
    if n <= 1:
        return [(start, end)]

    step = span / n
    out: list[tuple[float, float]] = []
    for i in range(n):
        a = start + i * step
        b = end if i == n - 1 else start + (i + 1) * step
        if b - a >= float(min_shot_duration_sec):
            out.append((a, b))
    return out or [(start, end)]


def plan_shot_batches(
    video_path: Path,
    *,
    scene_threshold: float = 0.35,
    max_shots_per_batch: int = 4,
    max_batch_duration_sec: float = 4.0,
    min_shot_duration_sec: float = 0.4,
    face_samples: int = 6,
    target_batch_duration_sec: float | None = None,
) -> dict[str, Any]:
    duration = _ffprobe_duration(video_path)
    if duration is None or duration <= 0.1:
        raise RuntimeError("Не удалось определить длительность видео для shot-batch plan.")

    # Preferred regenerable unit (default = Seedance min / max_batch).
    target_batch = float(
        target_batch_duration_sec
        if target_batch_duration_sec is not None
        else max_batch_duration_sec
    )
    if not math.isfinite(target_batch) or target_batch <= 0:
        target_batch = 4.0
    target_batch = max(4.0, target_batch)
    # Do not merge neighboring chunks past the regenerable unit.
    batch_dur_cap = min(float(max_batch_duration_sec), target_batch)
    if batch_dur_cap <= 0:
        batch_dur_cap = target_batch

    cut_times = _probe_scene_cut_times(video_path, scene_threshold=scene_threshold)
    # Build raw shots from 0 -> duration with cuts in between.
    all_points = [0.0] + [t for t in cut_times if 0 < t < duration] + [duration]
    all_points = sorted(all_points)

    scene_spans: list[tuple[float, float]] = []
    for a, b in zip(all_points, all_points[1:]):
        t0, t1 = float(a), float(b)
        if t1 - t0 < min_shot_duration_sec:
            continue
        scene_spans.append((t0, t1))
    if not scene_spans:
        scene_spans = [(0.0, duration)]

    shots_raw: list[tuple[float, float]] = []
    forced_chunks = False
    # Forced ~4s chunks only when scene-detect found nothing useful (one continuous
    # clip). If it already split into real scene parts, keep those as-is.
    if len(scene_spans) <= 1:
        t0, t1 = scene_spans[0]
        parts = _chunk_time_span(
            t0,
            t1,
            target_len=target_batch,
            min_shot_duration_sec=min_shot_duration_sec,
        )
        if len(parts) > 1:
            forced_chunks = True
        shots_raw = parts
        segmentation_mode = "duration_chunks" if forced_chunks else "scene_detect_single"
    else:
        shots_raw = list(scene_spans)
        segmentation_mode = "scene_detect"

    if not shots_raw:
        shots_raw = [(0.0, duration)]
        segmentation_mode = "scene_detect_single"

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

        if _should_start_new_batch_for_difficulty(cur, s):
            _flush()
            cur = [s]
            cur_dur = s.duration
            continue

        can_add = (
            len(cur) < max_shots_per_batch
            and (cur_dur + s.duration) <= batch_dur_cap + 1e-6
        )
        if can_add:
            cur.append(s)
            cur_dur += s.duration
        else:
            _flush()
            cur = [s]
            cur_dur = s.duration

    _flush()
    resolved_batches = _resolve_batches(batches, shots)

    return {
        "video_duration_sec": duration,
        "params": {
            "scene_threshold": scene_threshold,
            "max_shots_per_batch": max_shots_per_batch,
            "max_batch_duration_sec": max_batch_duration_sec,
            "target_batch_duration_sec": target_batch,
            "batch_duration_cap_sec": batch_dur_cap,
            "min_shot_duration_sec": min_shot_duration_sec,
            "face_samples": face_samples,
        },
        "segmentation_mode": segmentation_mode,
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
        "resolved_batches": [
            {
                "id": rb.id,
                "source_batch_id": rb.source_batch_id,
                "shot_ids": rb.shot_ids,
                "effective_shot_ids": rb.effective_shot_ids,
                "effective_t_start": rb.effective_t_start,
                "effective_t_end": rb.effective_t_end,
                "effective_duration": rb.effective_duration,
                "resolution_action": rb.resolution_action,
                "requires_synthetic_opening_frame": rb.requires_synthetic_opening_frame,
                "manual_review_required": rb.manual_review_required,
                "reason": rb.reason,
                "identity_string_policy": rb.identity_string_policy,
                "object_risk_level": rb.object_risk_level,
            }
            for rb in resolved_batches
        ],
    }


def _normalize_manual_cut_times(
    cut_times: list[float] | None,
    *,
    duration: float,
    min_batch_duration_sec: float,
) -> list[float]:
    """Interior cut points only (excluding 0 and duration), sorted and deduped."""
    min_dur = float(min_batch_duration_sec)
    if not math.isfinite(min_dur) or min_dur <= 0:
        min_dur = 0.4
    eps = max(0.05, min_dur * 0.25)
    raw = [float(t) for t in (cut_times or []) if math.isfinite(float(t))]
    interior = sorted({round(t, 3) for t in raw if eps < t < (duration - eps)})
    # Drop cuts that would create a segment shorter than min_dur.
    points = [0.0]
    for t in interior:
        if (t - points[-1]) >= min_dur - 1e-6:
            points.append(t)
    if (duration - points[-1]) < min_dur - 1e-6 and len(points) > 1:
        points.pop()
    return points[1:]


def plan_shot_batches_from_cuts(
    video_path: Path,
    cut_times: list[float] | None = None,
    *,
    min_batch_duration_sec: float = 0.4,
    max_batch_duration_sec: float | None = None,
) -> dict[str, Any]:
    """
    Build a shot-batch plan from manual timeline cut points.

    Each segment between cuts becomes one shot and one resolved batch.
    Face heuristics are skipped — openings/continuity stay under wizard control.
    """
    duration = _ffprobe_duration(video_path)
    if duration is None or duration <= 0.1:
        raise RuntimeError("Не удалось определить длительность видео для manual shot-batch plan.")

    min_dur = float(min_batch_duration_sec)
    if not math.isfinite(min_dur) or min_dur <= 0:
        min_dur = 0.4
    max_dur = float(max_batch_duration_sec) if max_batch_duration_sec is not None else 0.0
    if not math.isfinite(max_dur) or max_dur <= 0:
        max_dur = 0.0

    interior = _normalize_manual_cut_times(
        cut_times,
        duration=duration,
        min_batch_duration_sec=min_dur,
    )
    points = [0.0] + interior + [duration]
    spans: list[tuple[float, float]] = []
    for a, b in zip(points, points[1:]):
        t0, t1 = float(a), float(b)
        if t1 - t0 < min_dur - 1e-6:
            raise RuntimeError(
                f"Слишком короткий батч {t0:.2f}–{t1:.2f}s "
                f"(минимум {min_dur:.2f}s). Сдвинь точки нарезки."
            )
        spans.append((t0, t1))
    if not spans:
        spans = [(0.0, duration)]

    shots: list[ShotPlan] = []
    batches: list[BatchPlan] = []
    for idx, (t0, t1) in enumerate(spans, start=1):
        dur = t1 - t0
        shot = ShotPlan(
            id=idx,
            t_start=t0,
            t_end=t1,
            duration=dur,
            subject_visibility_status="uncertain",
            difficulty="medium",
            face_hits=0,
            object_risk_level="medium",
            motion_score=0.0,
        )
        shots.append(shot)
        batches.append(
            BatchPlan(
                id=idx,
                shot_ids=[idx],
                t_start=t0,
                t_end=t1,
                duration=dur,
                has_subject=True,
                identity_anchor_visible=True,
                object_risk_level="medium",
                risky=bool(max_dur > 0 and dur > max_dur + 1e-6),
                risky_reason=(
                    f"batch longer than max_batch_duration_sec={max_dur:.2f}"
                    if max_dur > 0 and dur > max_dur + 1e-6
                    else None
                ),
            )
        )

    resolved_batches = [
        ResolvedBatchPlan(
            id=b.id,
            source_batch_id=b.id,
            shot_ids=list(b.shot_ids),
            effective_shot_ids=list(b.shot_ids),
            effective_t_start=b.t_start,
            effective_t_end=b.t_end,
            effective_duration=b.duration,
            resolution_action="manual_cuts",
            requires_synthetic_opening_frame=False,
            manual_review_required=False,
            reason="manual timeline cuts",
            identity_string_policy="immutable_job_level_string",
            object_risk_level=b.object_risk_level,
        )
        for b in batches
    ]

    return {
        "video_duration_sec": duration,
        "params": {
            "min_batch_duration_sec": min_dur,
            "max_batch_duration_sec": max_dur or None,
            "cut_times": interior,
        },
        "segmentation_mode": "manual_cuts",
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
        "resolved_batches": [
            {
                "id": rb.id,
                "source_batch_id": rb.source_batch_id,
                "shot_ids": rb.shot_ids,
                "effective_shot_ids": rb.effective_shot_ids,
                "effective_t_start": rb.effective_t_start,
                "effective_t_end": rb.effective_t_end,
                "effective_duration": rb.effective_duration,
                "resolution_action": rb.resolution_action,
                "requires_synthetic_opening_frame": rb.requires_synthetic_opening_frame,
                "manual_review_required": rb.manual_review_required,
                "reason": rb.reason,
                "identity_string_policy": rb.identity_string_policy,
                "object_risk_level": rb.object_risk_level,
            }
            for rb in resolved_batches
        ],
    }


def cut_times_from_plan(plan: dict[str, Any]) -> list[float]:
    """Interior cut points derived from resolved batches (or raw batches)."""
    resolved = plan.get("resolved_batches") or []
    if isinstance(resolved, list) and len(resolved) >= 2:
        return [
            round(float(rb.get("effective_t_end") or 0.0), 3)
            for rb in resolved[:-1]
            if float(rb.get("effective_t_end") or 0.0) > 0
        ]
    batches = plan.get("batches") or []
    if isinstance(batches, list) and len(batches) >= 2:
        return [
            round(float(b.get("t_end") or 0.0), 3)
            for b in batches[:-1]
            if float(b.get("t_end") or 0.0) > 0
        ]
    return []

