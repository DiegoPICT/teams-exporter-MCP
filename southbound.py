import asyncio
from contextlib import suppress

from fastapi import WebSocket

from logging_helper import get_logger

logger = get_logger(__name__)


class ExtensionSession:
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self._send_lock = asyncio.Lock()
        self.client = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"

    async def send_frame(self, frame: dict) -> None:
        async with self._send_lock:
            await self.websocket.send_json(frame)

    async def close(self, code: int, reason: str) -> None:
        logger.info("event=southbound_socket_close_initiated client=%s code=%s reason=%s", self.client, code, reason)
        with suppress(Exception):
            await self.websocket.close(code=code, reason=reason)
