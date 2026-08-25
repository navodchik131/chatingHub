from pathlib import Path

from app.config import BACKEND_DIR
from app.services.studio_seedance_director import (
    _director_instruction_candidates,
    assemble_director_instruction,
    duration_from_span,
    parse_director_response,
    variant_for_piece_version,
)


def test_instruction_loads_from_bundled_prompts() -> None:
    bundled = (BACKEND_DIR / "_bundled_prompts" / "seedance_director_instruction.txt").resolve()
    assert bundled.is_file(), f"missing bundled prompt: {bundled}"
    paths = _director_instruction_candidates()
    assert any("_bundled_prompts" in str(p) for p in paths)
    text = assemble_director_instruction(
        what_happens="test",
        duration_seconds=10,
        aspect_ratio="9:16",
        camera_mode="C",
        image_roles=["first frame"],
    )
    assert "{{MY_BRIEF_BLOCK}}" not in text


def test_assemble_injects_brief_and_roles():
    text = assemble_director_instruction(
        what_happens="she looks at the window",
        duration_seconds=15,
        aspect_ratio="9:16",
        camera_mode="A",
        image_roles=["first frame", "face", "body"],
    )
    assert "{{MY_BRIEF_BLOCK}}" not in text
    assert "she looks at the window" in text
    assert "Image 1 — first frame" in text
    assert "Camera mode A" in text
    assert "Seedance 2.0" in text


def test_parse_fenced_pieces():
    sample = """Seedance 2.0 — 1a — 0.0–10.0s

```
prompt twenty
```

Seedance 2.5 — 1a — 0.0–20.0s

Start frame: mid-step, phone at chest

```
prompt twenty five
```

Assumed: she is alone
"""
    r = parse_director_response(sample)
    assert len(r.pieces) == 2
    assert r.pieces[0].version == "2.0"
    assert r.pieces[0].prompt == "prompt twenty"
    assert r.pieces[1].version == "2.5"
    assert r.pieces[1].prompt == "prompt twenty five"
    assert "mid-step" in r.pieces[1].start_frame
    assert r.assumed == "she is alone"


def test_variant_and_duration():
    assert variant_for_piece_version("2.5") == "seedance_25"
    assert variant_for_piece_version("2.0") == "standard"
    assert duration_from_span("0.0–12.0s", fallback=10, version="2.0") == 12
    assert duration_from_span("0-40s", fallback=10, version="2.5") == 30


def test_director_pricing():
    from app.services.studio_seedance_director_pricing import (
        seedance_director_compose_credit_cost,
        seedance_director_piece_credit_cost,
    )

    assert seedance_director_compose_credit_cost(image_count=1) >= 1
    assert seedance_director_compose_credit_cost(image_count=3) >= seedance_director_compose_credit_cost(image_count=1)
    assert seedance_director_piece_credit_cost(
        version="2.0", duration_seconds=10, resolution="720p", video_backend="wavespeed"
    ) >= 1
    assert seedance_director_piece_credit_cost(
        version="2.5", duration_seconds=15, resolution="720p", video_backend="evolink"
    ) >= 1


def test_director_generate_job_type_registered() -> None:
    from app.services.studio_jobs import STUDIO_JOB_TYPES

    assert "seedance_director_generate" in STUDIO_JOB_TYPES
