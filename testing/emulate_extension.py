#!/usr/bin/env python3
import argparse
import asyncio
import json
import time
import uuid
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
    return f"type={frame.get('type')} requestId={frame.get('requestId')} payload={frame.get('payload')}"


def make_conversations(request_id: str) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "CONVERSATIONS",
        "requestId": request_id,
        "ts": now_ms(),
        "payload": {
            "conversations": [
                {
                    "id": "19:mock-1@thread.v2",
                    "title": "Mock Conversation 1",
                },
                {
                    "id": "19:mock-2@thread.v2",
                    "title": "Mock Conversation 2",
                },
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
            "count": 2,
            "chunks": 1,
            "conversationId": "19:mock-1@thread.v2",
            "conversationTitle": "Mock Conversation 1",
        },
    }


def make_chunk(request_id: str) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "CHUNK",
        "requestId": request_id,
        "ts": now_ms(),
        "payload": {
            "index": 0,
            "totalChunks": 1,
            "messages": [
                {
                    "id": "msg-1",
                    "author": "mock-user",
                    "text": "hello",
                    "ts": "2026-06-01T00:00:00.000Z",
                },
                {
                    "id": "msg-2",
                    "author": "mock-user",
                    "text": "world",
                    "ts": "2026-06-01T00:01:00.000Z",
                },
            ],
        },
    }


def make_done(request_id: str, cancelled: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {"count": 2}
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


async def emulate_extension(url: str, idle_timeout: float, tab_id: int, conversation_id: str, conversation_title: str) -> None:
    session_id = str(uuid.uuid4())

    async with websockets.connect(url) as ws:
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
                    response = make_conversations(request_id)
                else:
                    response = make_error(None, "UNSUPPORTED", "LIST_CONVERSATIONS missing requestId")
                await ws.send(json.dumps(response))
                print(f"[extension] tx {frame_summary(response)}")
                continue

            if frame_type == "START_SNAPSHOT":
                if not isinstance(request_id, str):
                    response = make_error(None, "UNSUPPORTED", "START_SNAPSHOT missing requestId")
                    await ws.send(json.dumps(response))
                    print(f"[extension] tx {frame_summary(response)}")
                    continue

                for outbound in (make_snapshot_started(request_id), make_chunk(request_id), make_done(request_id)):
                    await ws.send(json.dumps(outbound))
                    print(f"[extension] tx {frame_summary(outbound)}")
                continue

            if frame_type == "CANCEL":
                if isinstance(request_id, str):
                    response = make_done(request_id, cancelled=True)
                else:
                    response = make_done("cancel-without-request-id", cancelled=True)
                await ws.send(json.dumps(response))
                print(f"[extension] tx {frame_summary(response)}")
                continue

            response = make_error(
                request_id if isinstance(request_id, str) else None,
                "UNSUPPORTED",
                f"Unsupported command type: {frame_type}",
            )
            await ws.send(json.dumps(response))
            print(f"[extension] tx {frame_summary(response)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emulate extension-side behavior over bridge WebSocket.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--path", default="/ws")
    parser.add_argument("--idle-timeout", type=float, default=20.0)
    parser.add_argument("--tab-id", type=int, default=123)
    parser.add_argument("--conversation-id", default="19:mock-1@thread.v2")
    parser.add_argument("--conversation-title", default="Mock Conversation 1")
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
        )
    )


if __name__ == "__main__":
    main()
