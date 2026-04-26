from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class RealtimeHub:
    """События доставляются только WebSocket-клиентам указанного user_id."""

    def __init__(self) -> None:
        self._by_user: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, user_id: int) -> None:
        await ws.accept()
        async with self._lock:
            self._by_user.setdefault(user_id, set()).add(ws)

    async def disconnect(self, ws: WebSocket, user_id: int) -> None:
        async with self._lock:
            s = self._by_user.get(user_id)
            if not s:
                return
            s.discard(ws)
            if not s:
                del self._by_user[user_id]

    async def broadcast_user(self, user_id: int, event: dict[str, Any]) -> None:
        raw = json.dumps(event, ensure_ascii=False)
        async with self._lock:
            clients = list(self._by_user.get(user_id, ()))
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_text(raw)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                s = self._by_user.get(user_id)
                if not s:
                    return
                for w in dead:
                    s.discard(w)
                if not s:
                    del self._by_user[user_id]


hub = RealtimeHub()
