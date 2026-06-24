"""Временные референсы для workflow-редактора (до execute)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.config import BACKEND_DIR

WORKFLOW_REFS_ROOT = (BACKEND_DIR / "data" / "workflow_refs").resolve()
MAX_REF_BYTES = 25 * 1024 * 1024


def _owner_dir(owner_id: int) -> Path:
    d = WORKFLOW_REFS_ROOT / str(owner_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_workflow_reference(
    owner_id: int,
    data: bytes,
    *,
    content_type: str,
) -> str:
    if len(data) > MAX_REF_BYTES:
        raise ValueError(
            f"Файл слишком большой (макс. {MAX_REF_BYTES // (1024 * 1024)} МБ)"
        )
    ref_id = uuid.uuid4().hex
    owner_dir = _owner_dir(owner_id)
    meta = {"content_type": (content_type or "image/jpeg").split(";")[0].strip()}
    (owner_dir / f"{ref_id}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    (owner_dir / f"{ref_id}.bin").write_bytes(data)
    return ref_id


def load_workflow_reference(owner_id: int, ref_id: str) -> tuple[bytes, str]:
    rid = (ref_id or "").strip()
    if not rid or "/" in rid or ".." in rid:
        raise ValueError("Некорректный ref_id")
    owner_dir = _owner_dir(owner_id)
    bin_path = (owner_dir / f"{rid}.bin").resolve()
    meta_path = (owner_dir / f"{rid}.meta.json").resolve()
    try:
        bin_path.relative_to(owner_dir.resolve())
        meta_path.relative_to(owner_dir.resolve())
    except ValueError:
        raise ValueError("Некорректный ref_id") from None
    if not bin_path.is_file():
        raise FileNotFoundError("Референс не найден или истёк")
    mime = "image/jpeg"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(meta.get("content_type"), str):
                mime = meta["content_type"]
        except json.JSONDecodeError:
            pass
    return bin_path.read_bytes(), mime
