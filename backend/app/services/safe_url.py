"""Проверка HTTPS URL перед server-side fetch (защита от SSRF)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException

# Запрещённые hostname (cloud metadata и т.п.)
_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.goog",
    }
)


def _is_blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _resolve_host_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise HTTPException(status_code=400, detail="Некорректный URL хоста") from e
    addrs: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_str = sockaddr[0]
        try:
            addrs.append(ipaddress.ip_address(ip_str))
        except ValueError:
            continue
    if not addrs:
        raise HTTPException(status_code=400, detail="Не удалось разрешить URL хоста")
    return addrs


def assert_safe_https_url(url: str, *, field: str = "URL") -> str:
    """Разрешает только публичные https:// URL без private/reserved IP."""
    u = (url or "").strip()
    parsed = urlparse(u)
    if parsed.scheme.lower() != "https":
        raise HTTPException(status_code=400, detail=f"{field}: нужен https://")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise HTTPException(status_code=400, detail=f"{field}: пустой хост")
    if host in _BLOCKED_HOSTS:
        raise HTTPException(status_code=400, detail=f"{field}: хост запрещён")
    # Литеральный IP в URL
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip):
            raise HTTPException(status_code=400, detail=f"{field}: внутренний адрес запрещён")
        return u
    except ValueError:
        pass
    for addr in _resolve_host_ips(host):
        if _is_blocked_ip(addr):
            raise HTTPException(status_code=400, detail=f"{field}: внутренний адрес запрещён")
    return u


async def safe_https_download_bytes(
    url: str,
    *,
    timeout: float,
    max_redirects: int = 5,
) -> tuple[bytes, str | None]:
    """GET по HTTPS с ручной проверкой каждого redirect."""
    current = assert_safe_https_url(url)
    last_ct: str | None = None
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(max_redirects + 1):
            resp = await client.get(current)
            if resp.status_code in {301, 302, 303, 307, 308}:
                loc = (resp.headers.get("location") or "").strip()
                if not loc:
                    resp.raise_for_status()
                current = assert_safe_https_url(urljoin(current, loc))
                continue
            resp.raise_for_status()
            last_ct = (resp.headers.get("content-type") or "").split(";")[0].strip().lower() or None
            return resp.content, last_ct
    raise HTTPException(status_code=400, detail="Слишком много redirect")
