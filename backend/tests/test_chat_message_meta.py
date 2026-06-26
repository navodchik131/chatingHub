"""Реакции и мета сообщений."""

from __future__ import annotations

from app.services.chat_message_meta import (
    parse_reactions,
    sync_actor_reactions,
    toggle_owner_reaction,
)


def test_toggle_owner_reaction_add_and_remove():
    base = [{"emoji": "👍", "actor": "peer"}]
    with_owner = toggle_owner_reaction(base, "❤️")
    assert {"emoji": "❤️", "actor": "owner"} in with_owner
    without = toggle_owner_reaction(with_owner, "❤️")
    assert not any(r["emoji"] == "❤️" and r["actor"] == "owner" for r in without)
    assert any(r["emoji"] == "👍" and r["actor"] == "peer" for r in without)


def test_sync_actor_reactions_replaces_peer_only():
    base = [
        {"emoji": "👍", "actor": "owner"},
        {"emoji": "😂", "actor": "peer"},
    ]
    synced = sync_actor_reactions(base, actor="peer", emojis=["❤️"])
    assert {"emoji": "👍", "actor": "owner"} in synced
    assert {"emoji": "❤️", "actor": "peer"} in synced
    assert not any(r["actor"] == "peer" and r["emoji"] == "😂" for r in synced)


def test_parse_reactions_invalid_json():
    assert parse_reactions("{not json") == []
