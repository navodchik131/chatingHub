"""Сигнал устройства/браузера для анти-абуза демо-генераций."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from starlette.requests import Request

_DEVICE_ID_RE = re.compile(r"^[a-zA-Z0-9._-]{8,128}$")


@dataclass(frozen=True)
class DeviceSignal:
    device_key: str
    ip_hash: str
    ua_hash: str
    fp_hash: str | None


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_client_device_id(raw: str | None) -> str | None:
    token = (raw or "").strip()
    if not token or not _DEVICE_ID_RE.fullmatch(token):
        return None
    return token


def client_ip_from_request(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def build_device_signal(
    *,
    client_ip: str,
    user_agent: str,
    device_id: str | None = None,
) -> DeviceSignal:
    ip_hash = _sha256_hex(client_ip.strip() or "unknown")
    ua_hash = _sha256_hex((user_agent or "")[:512])
    fp = normalize_client_device_id(device_id)
    fp_hash = _sha256_hex(fp) if fp else None
    material = f"{ip_hash}:{ua_hash}" if not fp_hash else f"{ip_hash}:{ua_hash}:{fp_hash}"
    return DeviceSignal(
        device_key=_sha256_hex(material),
        ip_hash=ip_hash,
        ua_hash=ua_hash,
        fp_hash=fp_hash,
    )


def device_signal_from_request(request: Request) -> DeviceSignal:
    device_id = request.headers.get("x-device-id")
    return build_device_signal(
        client_ip=client_ip_from_request(request),
        user_agent=request.headers.get("user-agent") or "",
        device_id=device_id,
    )


def merge_device_key_into_params(params: dict, request: Request) -> None:
    sig = device_signal_from_request(request)
    params["device_key"] = sig.device_key
    params["device_ip_hash"] = sig.ip_hash
    params["device_ua_hash"] = sig.ua_hash
    if sig.fp_hash:
        params["device_fp_hash"] = sig.fp_hash


def device_signal_from_mapping(data: dict | None) -> DeviceSignal | None:
    if not data:
        return None
    device_key = str(data.get("device_key") or "").strip()
    if not device_key:
        return None
    return DeviceSignal(
        device_key=device_key,
        ip_hash=str(data.get("device_ip_hash") or "").strip() or _sha256_hex("unknown"),
        ua_hash=str(data.get("device_ua_hash") or "").strip() or _sha256_hex(""),
        fp_hash=(str(data.get("device_fp_hash") or "").strip() or None),
    )


def device_key_from_mapping(data: dict | None) -> str | None:
    if not data:
        return None
    key = str(data.get("device_key") or "").strip()
    return key or None
