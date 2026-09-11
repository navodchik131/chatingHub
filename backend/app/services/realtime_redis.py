"""Redis pub/sub для RealtimeHub — синхрон WS между несколькими API-инстансами."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

log = logging.getLogger(__name__)

REALTIME_CHANNEL = "mm:realtime"


class RedisRealtimeBridge:
    """Публикует события в Redis; подписчик доставляет их локальным WebSocket-клиентам."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: Any = None
        self._pubsub: Any = None
        self._listen_task: asyncio.Task[None] | None = None
        self._deliver: Any = None

    async def start(self, deliver_local) -> None:
        """deliver_local(user_id, event) — callback RealtimeHub."""
        import redis.asyncio as redis

        self._deliver = deliver_local
        self._redis = redis.from_url(self._redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(REALTIME_CHANNEL)
        self._listen_task = asyncio.create_task(self._listen_loop())
        log.info("Redis realtime bridge subscribed: %s", REALTIME_CHANNEL)

    async def stop(self) -> None:
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.unsubscribe(REALTIME_CHANNEL)
            await self._pubsub.aclose()
        if self._redis:
            await self._redis.aclose()

    async def publish(self, user_id: int, event: dict[str, Any]) -> None:
        if not self._redis:
            return
        payload = json.dumps({"user_id": user_id, "event": event}, ensure_ascii=False)
        await self._redis.publish(REALTIME_CHANNEL, payload)

    async def _listen_loop(self) -> None:
        assert self._pubsub is not None
        while True:
            try:
                msg = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg or msg.get("type") != "message":
                    continue
                data = json.loads(msg["data"])
                user_id = int(data["user_id"])
                event = data["event"]
                if self._deliver:
                    await self._deliver(user_id, event)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Redis realtime listen error")
                await asyncio.sleep(1.0)
