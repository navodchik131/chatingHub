from app.services.studio_jobs import (
    StudioJob,
    motion_render_video_dedupe_key,
    studio_job_provider_submitted,
)


def test_motion_render_video_dedupe_key_stable():
    params = {
        "video_backend": "evolink",
        "model_id": 1,
        "motion_video_file_id": "abc",
        "turnaround_generation_id": "42",
        "trim_mode": "part",
        "trim_start_sec": 1.0,
        "trim_end_sec": 8.0,
        "duration_seconds": "8",
    }
    k1 = motion_render_video_dedupe_key(params)
    k2 = motion_render_video_dedupe_key(dict(params))
    assert k1 == k2
    assert k1.startswith("motion-video:")


def test_motion_render_video_dedupe_key_differs_on_trim():
    base = {
        "video_backend": "wavespeed",
        "model_id": 1,
        "motion_video_file_id": "abc",
        "trim_mode": "part",
        "trim_start_sec": 0,
        "trim_end_sec": 5,
    }
    other = dict(base)
    other["trim_end_sec"] = 6
    assert motion_render_video_dedupe_key(base) != motion_render_video_dedupe_key(other)


def test_studio_job_provider_submitted_flag():
    job = StudioJob(params_json='{"provider_submitted":"1"}')
    assert studio_job_provider_submitted(job) is True
    job2 = StudioJob(params_json='{"provider_submitted":"0"}')
    assert studio_job_provider_submitted(job2) is False
