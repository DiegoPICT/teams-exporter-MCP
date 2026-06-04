import asyncio
from contextlib import suppress

from fastapi import WebSocket


class ExtensionSession:
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self._send_lock = asyncio.Lock()

    async def send_frame(self, frame: dict) -> None:
        async with self._send_lock:
            await self.websocket.send_json(frame)

    async def close(self, code: int, reason: str) -> None:
        with suppress(Exception):
            await self.websocket.close(code=code, reason=reason)
