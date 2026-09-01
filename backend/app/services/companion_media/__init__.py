"""Медиатека companion bot."""

from app.services.companion_media.library import (
    create_media_asset_from_generation,
    create_media_asset_from_upload,
    delete_media_asset,
    delete_media_pack,
    get_media_asset_owned,
    list_media_assets,
    list_media_packs,
    get_media_asset_owned,
    mark_media_sent,
    reindex_media_embeddings,
    update_media_asset,
    update_media_pack,
    create_media_pack,
)
from app.services.companion_media.search import pick_companion_media
from app.services.companion_media.storage import resolve_companion_media_file

__all__ = [
    "create_media_pack",
    "create_media_asset_from_upload",
    "create_media_asset_from_generation",
    "delete_media_pack",
    "delete_media_asset",
    "list_media_packs",
    "list_media_assets",
    "update_media_pack",
    "update_media_asset",
    "reindex_media_embeddings",
    "mark_media_sent",
    "pick_companion_media",
    "resolve_companion_media_file",
]
