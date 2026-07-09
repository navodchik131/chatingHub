"""Tests for Fanvue peer unavailable detection."""

from app.services.fanvue_peer_status import fanvue_api_body_indicates_invalid_user


def test_fanvue_invalid_user_plain_text():
    assert fanvue_api_body_indicates_invalid_user('{"message":"Invalid user UUID"}')


def test_fanvue_invalid_user_message_field():
    assert fanvue_api_body_indicates_invalid_user('{"message":"Invalid user UUID"}')


def test_fanvue_invalid_user_unrelated():
    assert not fanvue_api_body_indicates_invalid_user('{"message":"Rate limit exceeded"}')
    assert not fanvue_api_body_indicates_invalid_user("")
