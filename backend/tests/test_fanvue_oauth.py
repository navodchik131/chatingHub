"""Tests for Fanvue OAuth helpers."""

from app.connectors.fanvue.client import fanvue_user_facing_error
from app.connectors.fanvue.oauth import (
    FANVUE_DEFAULT_OAUTH_SCOPES,
    fanvue_oauth_scopes,
    generate_oauth_state,
    generate_pkce_pair,
)


def test_generate_pkce_pair_lengths():
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert verifier != challenge


def test_generate_oauth_state_unique():
    a = generate_oauth_state()
    b = generate_oauth_state()
    assert a != b
    assert len(a) >= 16


def test_fanvue_default_scopes_include_media_upload():
    scopes = fanvue_oauth_scopes()
    for required in ("write:chat", "write:media", "write:creator", "read:media"):
        assert required in scopes


def test_fanvue_default_scopes_constant():
    assert "write:media" in FANVUE_DEFAULT_OAUTH_SCOPES
    assert "write:creator" in FANVUE_DEFAULT_OAUTH_SCOPES


def test_fanvue_user_facing_insufficient_scopes():
    msg = fanvue_user_facing_error('{"error":"Insufficient scopes"}')
    assert msg
    assert "write:media" in msg
