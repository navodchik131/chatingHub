"""Тесты медиатеки companion bot."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.companion_media.library import build_asset_embed_text
from app.services.companion_media.search import expand_pack_assets


def _asset(aid: int, sort_order: int, status: str = "active") -> SimpleNamespace:
    return SimpleNamespace(id=aid, sort_order=sort_order, status=status)


def test_build_asset_embed_text_includes_series_and_tags() -> None:
    text = build_asset_embed_text(
        title="Shower selfie",
        description="Wet hair, white towel",
        tags=["shower", "tease"],
        pack_name="Morning routine",
        pack_description="4 photos from bathroom",
        pack_tags=["bathroom"],
        media_type="photo",
    )
    assert "Shower selfie" in text
    assert "tags:" in text
    assert "shower" in text
    assert "series: Morning routine" in text
    assert "type: photo" in text


def test_expand_pack_starts_from_matched_and_skips_sent() -> None:
    assets = [_asset(1, 1), _asset(2, 2), _asset(3, 3), _asset(4, 4), _asset(5, 5)]
    picked = expand_pack_assets(
        pack_assets=assets,
        matched_asset_id=3,
        sent_asset_ids={1, 2},
        max_send_count=4,
    )
    assert [a.id for a in picked] == [3, 4, 5]


def test_expand_pack_wraps_when_fewer_than_max() -> None:
    assets = [_asset(1, 1), _asset(2, 2), _asset(3, 3)]
    picked = expand_pack_assets(
        pack_assets=assets,
        matched_asset_id=2,
        sent_asset_ids=set(),
        max_send_count=4,
    )
    assert [a.id for a in picked] == [2, 3, 1]


def test_expand_pack_returns_empty_when_all_sent() -> None:
    assets = [_asset(1, 1), _asset(2, 2)]
    picked = expand_pack_assets(
        pack_assets=assets,
        matched_asset_id=1,
        sent_asset_ids={1, 2},
        max_send_count=4,
    )
    assert picked == []
