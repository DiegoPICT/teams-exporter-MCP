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
            "tabId": 700,
            "conversationId": "smoke:phase2",
            "conversationTitle": "Phase 2 Smoke",
        },
    }


def make_command(frame_type: str, request_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    frame: dict[str, Any] = {
        "v": PROTOCOL_VERSION,
        "type": frame_type,
        "requestId": request_id,
        "ts": now_ms(),
    }
    if payload is not None:
        frame["payload"] = payload
    return frame


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def recv_json(ws: websockets.ClientConnection, timeout: float = 8.0) -> dict[str, Any]:
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    assert_true(isinstance(raw, str), "Expected text websocket frame")
    frame = json.loads(raw)
    assert_true(isinstance(frame, dict), "Expected JSON object frame")
    return frame


async def send_json(ws: websockets.ClientConnection, frame: dict[str, Any]) -> None:
    await ws.send(json.dumps(frame))


def print_frame(direction: str, frame: dict[str, Any]) -> None:
    print(
        f"[{direction}] type={frame.get('type')} requestId={frame.get('requestId')} "
        f"payload={frame.get('payload')} error={frame.get('error')}"
    )


async def run_smoke(url: str) -> None:
    async with websockets.connect(url) as ws:
        await send_json(ws, make_hello())
        ack = await recv_json(ws)
        print_frame("rx", ack)
        assert_true(ack.get("type") == "HELLO_ACK", "Expected HELLO_ACK")

        list_req_id = "smoke-list-1"
        await send_json(ws, make_command("LIST_CONVERSATIONS", list_req_id))
        list_resp = await recv_json(ws)
        print_frame("rx", list_resp)
        assert_true(list_resp.get("type") == "CONVERSATIONS", "Expected CONVERSATIONS")
        assert_true(list_resp.get("requestId") == list_req_id, "LIST requestId must be echoed")

        snap_req_id = "smoke-snap-1"
        await send_json(ws, make_command("START_SNAPSHOT", snap_req_id))
        started = await recv_json(ws)
        print_frame("rx", started)
        assert_true(started.get("type") == "SNAPSHOT_STARTED", "Expected SNAPSHOT_STARTED")
        assert_true(started.get("requestId") == snap_req_id, "SNAPSHOT_STARTED requestId must be echoed")

        busy_req_id = "smoke-list-busy"
        await send_json(ws, make_command("LIST_CONVERSATIONS", busy_req_id))
        busy_resp = await recv_json(ws)
        print_frame("rx", busy_resp)
        assert_true(busy_resp.get("type") == "ERROR", "Expected ERROR while snapshot in progress")
        assert_true(busy_resp.get("requestId") == busy_req_id, "BUSY error must echo requestId")
        payload = busy_resp.get("payload") if isinstance(busy_resp.get("payload"), dict) else {}
        assert_true(payload.get("code") == "BUSY", "Expected BUSY code")

        await send_json(ws, make_command("CANCEL", snap_req_id))
        cancelled = await recv_json(ws)
        print_frame("rx", cancelled)
        assert_true(cancelled.get("type") == "DONE", "Expected DONE after CANCEL")
        assert_true(cancelled.get("requestId") == snap_req_id, "CANCEL DONE must echo snapshot requestId")
        cancelled_payload = cancelled.get("payload") if isinstance(cancelled.get("payload"), dict) else {}
        assert_true(cancelled_payload.get("cancelled") is True, "Expected cancelled=true")

        idempotent_cancel_id = "smoke-cancel-idempotent"
        await send_json(ws, make_command("CANCEL", idempotent_cancel_id))
        idempotent = await recv_json(ws)
        print_frame("rx", idempotent)
        assert_true(idempotent.get("type") == "DONE", "Expected idempotent CANCEL DONE")
        assert_true(idempotent.get("requestId") == idempotent_cancel_id, "Idempotent CANCEL must echo requestId")

    print("[ok] Phase 2 smoke checks passed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 2 websocket smoke checks against local bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--path", default="/ws")
    return parser.parse_args()


def build_url(host: str, port: int, path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    return f"ws://{host}:{port}{normalized}"


def main() -> None:
    args = parse_args()
    asyncio.run(run_smoke(build_url(args.host, args.port, args.path)))


if __name__ == "__main__":
    main()
