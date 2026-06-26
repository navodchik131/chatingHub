"""Tests for Fanvue history sync helpers."""

from app.connectors.fanvue.client import fanvue_api_data_list, fanvue_api_has_more
from app.services.fanvue_sync import _fanvue_chat_fan, _message_sort_key


def test_fanvue_api_data_list_from_dict():
    payload = {"data": [{"uuid": "a"}, {"uuid": "b"}]}
    assert len(fanvue_api_data_list(payload)) == 2


def test_fanvue_api_data_list_from_list():
    assert fanvue_api_data_list([{"x": 1}]) == [{"x": 1}]


def test_fanvue_api_has_more_pagination():
    payload = {"data": [1, 2], "pagination": {"hasMore": True}}
    assert fanvue_api_has_more(payload, page=1, page_size=2, fetched=2) is True
    payload["pagination"]["hasMore"] = False
    assert fanvue_api_has_more(payload, page=1, page_size=2, fetched=2) is False


def test_fanvue_chat_fan_user():
    uuid, display = _fanvue_chat_fan(
        {"user": {"uuid": "fan-1", "handle": "@fan_one", "displayName": "Fan One"}}
    )
    assert uuid == "fan-1"
    assert display == "Fan One"


def test_message_sort_key_uses_sent_at():
    a = {"uuid": "b", "sentAt": "2026-01-02T10:00:00Z"}
    b = {"uuid": "a", "sentAt": "2026-01-01T10:00:00Z"}
    assert _message_sort_key(a) > _message_sort_key(b)
