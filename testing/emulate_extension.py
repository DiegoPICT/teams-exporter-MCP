#!/usr/bin/env python3
import argparse
import asyncio
import json
import time
import uuid
from contextlib import suppress
from typing import Any

import websockets


PROTOCOL_VERSION = "teams-exporter-bridge/v1"


def now_ms() -> int:
    return int(time.time() * 1000)


def make_hello(session_id: str, tab_id: int, conversation_id: str, conversation_title: str) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "HELLO",
        "sessionId": session_id,
        "ts": now_ms(),
        "payload": {
            "protocol": PROTOCOL_VERSION,
            "tabId": tab_id,
            "conversationId": conversation_id,
            "conversationTitle": conversation_title,
        },
    }


def frame_summary(frame: dict[str, Any]) -> str:
    return f"type={frame.get('type')} requestId={frame.get('requestId')} payload={frame.get('payload')} error={frame.get('error')}"


def make_conversations(request_id: str) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "CONVERSATIONS",
        "requestId": request_id,
        "ts": now_ms(),
        "payload": {
            "conversations": [
                {"id": "19:mock-1@thread.v2", "title": "Mock Conversation 1"},
                {"id": "19:mock-2@thread.v2", "title": "Mock Conversation 2"},
            ],
            "folders": [],
        },
    }


def make_snapshot_started(request_id: str) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "SNAPSHOT_STARTED",
        "requestId": request_id,
        "ts": now_ms(),
        "payload": {
            "count": 6,
            "chunks": 3,
            "conversationId": "19:mock-1@thread.v2",
            "conversationTitle": "Mock Conversation 1",
        },
    }


def make_chunk(request_id: str, index: int, total_chunks: int) -> dict[str, Any]:
    base = index * 2
    return {
        "v": PROTOCOL_VERSION,
        "type": "CHUNK",
        "requestId": request_id,
        "ts": now_ms(),
        "payload": {
            "index": index,
            "totalChunks": total_chunks,
            "messages": [
                {
                    "id": f"msg-{base + 1}",
                    "author": "mock-user",
                    "text": f"message-{base + 1}",
                    "ts": "2026-06-01T00:00:00.000Z",
                },
                {
                    "id": f"msg-{base + 2}",
                    "author": "mock-user",
                    "text": f"message-{base + 2}",
                    "ts": "2026-06-01T00:01:00.000Z",
                },
            ],
        },
    }


def make_done(request_id: str, cancelled: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {"count": 6}
    if cancelled:
        payload = {"cancelled": True, "reason": "cancelled"}
    return {
        "v": PROTOCOL_VERSION,
        "type": "DONE",
        "requestId": request_id,
        "ts": now_ms(),
        "payload": payload,
    }


def make_error(request_id: str | None, code: str, error: str) -> dict[str, Any]:
    frame: dict[str, Any] = {
        "v": PROTOCOL_VERSION,
        "type": "ERROR",
        "ts": now_ms(),
        "payload": {"code": code},
        "error": error,
    }
    if request_id is not None:
        frame["requestId"] = request_id
    return frame


class ExtensionEmulator:
    def __init__(self, ws: websockets.ClientConnection, chunk_delay: float, chunk_count: int) -> None:
        self.ws = ws
        self.chunk_delay = chunk_delay
        self.chunk_count = max(1, chunk_count)
        self.snapshot_task: asyncio.Task[None] | None = None
        self.snapshot_request_id: str | None = None

    async def send(self, frame: dict[str, Any]) -> None:
        await self.ws.send(json.dumps(frame))
        print(f"[extension] tx {frame_summary(frame)}")

    async def start_snapshot(self, request_id: str) -> None:
        if self.snapshot_task is not None and not self.snapshot_task.done():
            await self.send(make_error(request_id, "BUSY", "Another operation is already running"))
            return

        self.snapshot_request_id = request_id
        self.snapshot_task = asyncio.create_task(self._stream_snapshot(request_id))

    async def _stream_snapshot(self, request_id: str) -> None:
        await self.send(make_snapshot_started(request_id))
        for index in range(self.chunk_count):
            await asyncio.sleep(self.chunk_delay)
            await self.send(make_chunk(request_id, index=index, total_chunks=self.chunk_count))
        await asyncio.sleep(self.chunk_delay)
        await self.send(make_done(request_id, cancelled=False))
        self.snapshot_request_id = None
        self.snapshot_task = None

    async def cancel_snapshot(self, request_id: str) -> None:
        if self.snapshot_task is None or self.snapshot_task.done() or self.snapshot_request_id is None:
            await self.send(make_done(request_id, cancelled=True))
            return

        if request_id != self.snapshot_request_id:
            await self.send(
                make_error(
                    request_id,
                    "UNSUPPORTED",
                    f"CANCEL requestId {request_id} does not match active snapshot {self.snapshot_request_id}",
                )
            )
            return

        self.snapshot_task.cancel()
        with suppress(asyncio.CancelledError):
            await self.snapshot_task
        self.snapshot_task = None
        self.snapshot_request_id = None
        await self.send(make_done(request_id, cancelled=True))


async def emulate_extension(
    url: str,
    idle_timeout: float,
    tab_id: int,
    conversation_id: str,
    conversation_title: str,
    chunk_delay: float,
    chunk_count: int,
) -> None:
    session_id = str(uuid.uuid4())

    async with websockets.connect(url) as ws:
        emulator = ExtensionEmulator(ws=ws, chunk_delay=chunk_delay, chunk_count=chunk_count)
        hello = make_hello(session_id, tab_id, conversation_id, conversation_title)
        await ws.send(json.dumps(hello))
        print(f"[extension] tx HELLO sessionId={session_id}")

        try:
            ack_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            ack = json.loads(ack_raw)
            print(f"[extension] rx {frame_summary(ack)}")
        except TimeoutError:
            print("[extension] no HELLO_ACK received (continuing)")

        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=idle_timeout)
            except TimeoutError:
                print(f"[extension] idle timeout reached ({idle_timeout}s), exiting")
                return

            frame = json.loads(raw)
            frame_type = frame.get("type")
            request_id = frame.get("requestId")
            print(f"[extension] rx {frame_summary(frame)}")

            if frame_type == "LIST_CONVERSATIONS":
                if isinstance(request_id, str):
                    await emulator.send(make_conversations(request_id))
                else:
                    await emulator.send(make_error(None, "UNSUPPORTED", "LIST_CONVERSATIONS missing requestId"))
                continue

            if frame_type == "START_SNAPSHOT":
                if not isinstance(request_id, str):
                    await emulator.send(make_error(None, "UNSUPPORTED", "START_SNAPSHOT missing requestId"))
                    continue
                await emulator.start_snapshot(request_id)
                continue

            if frame_type == "CANCEL":
                if not isinstance(request_id, str):
                    await emulator.send(make_error(None, "UNSUPPORTED", "CANCEL missing requestId"))
                    continue
                await emulator.cancel_snapshot(request_id)
                continue

            await emulator.send(
                make_error(
                    request_id if isinstance(request_id, str) else None,
                    "UNSUPPORTED",
                    f"Unsupported command type: {frame_type}",
                )
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emulate extension-side behavior over bridge WebSocket.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--path", default="/ws")
    parser.add_argument("--idle-timeout", type=float, default=40.0)
    parser.add_argument("--tab-id", type=int, default=123)
    parser.add_argument("--conversation-id", default="19:mock-1@thread.v2")
    parser.add_argument("--conversation-title", default="Mock Conversation 1")
    parser.add_argument("--chunk-delay", type=float, default=1.0)
    parser.add_argument("--chunk-count", type=int, default=3)
    return parser.parse_args()


def ws_url(host: str, port: int, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"ws://{host}:{port}{normalized_path}"


def main() -> None:
    args = parse_args()
    url = ws_url(args.host, args.port, args.path)
    asyncio.run(
        emulate_extension(
            url=url,
            idle_timeout=args.idle_timeout,
            tab_id=args.tab_id,
            conversation_id=args.conversation_id,
            conversation_title=args.conversation_title,
            chunk_delay=args.chunk_delay,
            chunk_count=args.chunk_count,
        )
    )


if __name__ == "__main__":
    main()
