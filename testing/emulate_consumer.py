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


def make_hello() -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "HELLO",
        "sessionId": str(uuid.uuid4()),
        "ts": now_ms(),
        "payload": {
            "protocol": PROTOCOL_VERSION,
            "tabId": 999,
            "conversationId": "consumer:test",
            "conversationTitle": "Consumer Test",
        },
    }


def make_frame(frame_type: str, request_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    frame: dict[str, Any] = {
        "v": PROTOCOL_VERSION,
        "type": frame_type,
        "requestId": request_id,
        "ts": now_ms(),
    }
    if payload is not None:
        frame["payload"] = payload
    return frame


def short(frame: dict[str, Any]) -> str:
    return f"type={frame.get('type')} requestId={frame.get('requestId')} payload={frame.get('payload')} error={frame.get('error')}"


async def recv_json(ws: websockets.ClientConnection, timeout: float) -> dict[str, Any]:
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    if not isinstance(raw, str):
        raise ValueError("received non-text frame")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("received non-object JSON frame")
    return data


async def handshake(ws: websockets.ClientConnection, timeout: float) -> None:
    hello = make_hello()
    await ws.send(json.dumps(hello))
    print("[consumer] tx HELLO")
    ack = await recv_json(ws, timeout)
    print(f"[consumer] rx {short(ack)}")
    if ack.get("type") != "HELLO_ACK":
        raise ValueError(f"expected HELLO_ACK, got {short(ack)}")


async def run_list(ws: websockets.ClientConnection, timeout: float) -> None:
    request_id = "req-list-1"
    frame = make_frame("LIST_CONVERSATIONS", request_id)
    await ws.send(json.dumps(frame))
    print(f"[consumer] tx {short(frame)}")
    response = await recv_json(ws, timeout)
    print(f"[consumer] rx {short(response)}")


async def run_snapshot(ws: websockets.ClientConnection, timeout: float) -> None:
    request_id = "req-snap-1"
    frame = make_frame(
        "START_SNAPSHOT",
        request_id,
        payload={
            "includeReplies": True,
            "includeReactions": True,
            "includeSystem": False,
        },
    )
    await ws.send(json.dumps(frame))
    print(f"[consumer] tx {short(frame)}")

    started = await recv_json(ws, timeout)
    print(f"[consumer] rx {short(started)}")

    done = await recv_json(ws, timeout + 5.0)
    print(f"[consumer] rx {short(done)}")


async def run_cancel(ws: websockets.ClientConnection, timeout: float, cancel_delay: float) -> None:
    snapshot_request_id = "req-snap-cancel-1"
    start_frame = make_frame("START_SNAPSHOT", snapshot_request_id)
    await ws.send(json.dumps(start_frame))
    print(f"[consumer] tx {short(start_frame)}")

    started = await recv_json(ws, timeout)
    print(f"[consumer] rx {short(started)}")

    await asyncio.sleep(cancel_delay)

    cancel_frame = make_frame("CANCEL", snapshot_request_id)
    await ws.send(json.dumps(cancel_frame))
    print(f"[consumer] tx {short(cancel_frame)}")

    done = await recv_json(ws, timeout)
    print(f"[consumer] rx {short(done)}")


async def run_consumer(url: str, timeout: float, mode: str, cancel_delay: float) -> None:
    async with websockets.connect(url) as ws:
        await handshake(ws, timeout=timeout)

        if mode in {"list", "all"}:
            await run_list(ws, timeout=timeout)

        if mode in {"snapshot", "all"}:
            await run_snapshot(ws, timeout=timeout)

        if mode in {"cancel", "all"}:
            await run_cancel(ws, timeout=timeout, cancel_delay=cancel_delay)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emulate a consumer issuing bridge app verbs.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--path", default="/ws")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--cancel-delay", type=float, default=0.25)
    parser.add_argument(
        "--mode",
        choices=["list", "snapshot", "cancel", "all"],
        default="all",
        help="Which verb flows to test",
    )
    return parser.parse_args()


def ws_url(host: str, port: int, path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    return f"ws://{host}:{port}{normalized}"


def main() -> None:
    args = parse_args()
    url = ws_url(args.host, args.port, args.path)
    asyncio.run(
        run_consumer(
            url=url,
            timeout=args.timeout,
            mode=args.mode,
            cancel_delay=args.cancel_delay,
        )
    )


if __name__ == "__main__":
    main()
