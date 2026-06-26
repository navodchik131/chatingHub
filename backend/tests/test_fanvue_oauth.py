"""Tests for Fanvue OAuth helpers."""

from app.connectors.fanvue.oauth import generate_pkce_pair, generate_oauth_state


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
