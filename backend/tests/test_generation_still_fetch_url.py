from types import SimpleNamespace

from app.services.studio_generation_status import StudioGenerationStatus
from app.services.studio_seedance_t2v import (
    generation_still_fetch_url,
    generation_still_public_url,
)


def _row(**kwargs):
    defaults = {
        "id": 42,
        "status": StudioGenerationStatus.READY,
        "relative_path": "",
        "source_url": "",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_generation_still_fetch_url_uses_cdn_when_no_local_archive():
    row = _row(
        status=StudioGenerationStatus.PROVIDER_READY,
        source_url="https://cdn.example/wavespeed/frame.png",
    )
    url = generation_still_fetch_url(
        row=row,
        owner_id=1,
        public_app_base="https://model-mate.online",
        token_factory=lambda **_: "tok",
    )
    assert url == "https://cdn.example/wavespeed/frame.png"


def test_generation_still_fetch_url_uses_public_url_when_archived(monkeypatch):
    row = _row(relative_path="data/gen/42.png")

    def _has_file(_row):
        return True

    monkeypatch.setattr(
        "app.services.studio_generation_storage.generation_has_archive_file",
        _has_file,
    )
    url = generation_still_fetch_url(
        row=row,
        owner_id=7,
        public_app_base="https://model-mate.online",
        token_factory=lambda user_id, generation_id: f"u{user_id}g{generation_id}",
    )
    expected = generation_still_public_url(
        owner_id=7,
        generation_id=42,
        public_app_base="https://model-mate.online",
        token_factory=lambda user_id, generation_id: f"u{user_id}g{generation_id}",
    )
    assert url == expected
    assert "public-generation-image" in (url or "")
