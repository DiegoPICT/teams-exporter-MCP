import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextlib import suppress

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from frame_helper import PROTOCOL_VERSION, make_error, make_frame
from logging_helper import get_log_file_path, setup_canonical_logging


load_dotenv()


HOST = os.getenv("BRIDGE_HOST", "127.0.0.1")
PORT = int(os.getenv("BRIDGE_PORT", "8765"))
WS_PATH = os.getenv("BRIDGE_PATH", "/ws")

logger = logging.getLogger("teams_bridge")


class BridgeState:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.active_websocket: WebSocket | None = None


state = BridgeState()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global logger
    logger = setup_canonical_logging("teams_bridge")
    logger.info(
        "event=bridge_started host=%s port=%s path=%s protocol=%s log_file=%s",
        HOST,
        PORT,
        WS_PATH,
        PROTOCOL_VERSION,
        get_log_file_path(),
    )
    try:
        yield
    finally:
        logger.info("event=bridge_stopping")
        await close_active_websocket()
        logger.info("event=bridge_stopped")


app = FastAPI(title="Teams Chat Exporter MCP Bridge", version="0.1.0", lifespan=lifespan)


async def close_active_websocket() -> None:
    ws = state.active_websocket
    if ws is None:
        return

    with suppress(Exception):
        await ws.close(code=1001, reason="Server shutting down")


def parse_json_message(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON frame") from exc

    if not isinstance(data, dict):
        raise ValueError("Frame must be a JSON object")

    return data


def validate_hello(frame: dict) -> None:
    frame_type = frame.get("type")
    version = frame.get("v")

    if frame_type != "HELLO":
        raise ValueError("First frame must be HELLO")

    if version != PROTOCOL_VERSION:
        raise ValueError(f"Protocol mismatch: expected {PROTOCOL_VERSION}")


async def send_hello_ack(websocket: WebSocket) -> None:
    ack = make_frame("HELLO_ACK")
    await websocket.send_json(ack)
    logger.info("event=hello_ack_sent")


async def send_unsupported_error(websocket: WebSocket, request_id: str | None) -> None:
    error_frame = make_error(
        request_id=request_id,
        code="UNSUPPORTED",
        error="Phase 1 bridge supports handshake only",
    )
    await websocket.send_json(error_frame)


@app.websocket("/{full_path:path}")
async def websocket_bridge(websocket: WebSocket, full_path: str) -> None:
    client = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    request_path = "/" + full_path

    if request_path != WS_PATH:
        await websocket.accept()
        await websocket.close(code=1008, reason=f"Unsupported path: {request_path}")
        logger.warning(
            "event=connection_rejected_path client=%s path=%s expected_path=%s",
            client,
            request_path,
            WS_PATH,
        )
        return

    async with state.lock:
        if state.active_websocket is not None:
            await websocket.accept()
            await websocket.close(code=1013, reason="Another extension session is active")
            logger.warning("event=connection_rejected_busy client=%s", client)
            return
        state.active_websocket = websocket

    await websocket.accept()
    logger.info("event=client_connected client=%s", client)

    try:
        raw = await websocket.receive_text()
        hello_frame = parse_json_message(raw)
        validate_hello(hello_frame)

        payload = hello_frame.get("payload") if isinstance(hello_frame.get("payload"), dict) else {}
        logger.info(
            "event=hello_received session_id=%s tab_id=%s conversation_id=%s conversation_title=%s",
            hello_frame.get("sessionId"),
            payload.get("tabId"),
            payload.get("conversationId"),
            payload.get("conversationTitle"),
        )

        await send_hello_ack(websocket)

        while True:
            raw_message = await websocket.receive_text()
            frame = parse_json_message(raw_message)
            frame_type = frame.get("type")
            request_id = frame.get("requestId")

            logger.info(
                "event=frame_received type=%s request_id=%s",
                frame_type,
                request_id,
            )

            if frame_type != "HELLO":
                await send_unsupported_error(websocket, request_id)

    except WebSocketDisconnect as exc:
        logger.info("event=client_disconnected client=%s code=%s", client, exc.code)
    except ValueError as exc:
        logger.error("event=protocol_error client=%s error=%s", client, str(exc))
        with suppress(Exception):
            await websocket.close(code=1002, reason=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.exception("event=unexpected_error client=%s error=%s", client, str(exc))
        with suppress(Exception):
            await websocket.close(code=1011, reason="Internal server error")
    finally:
        async with state.lock:
            if state.active_websocket is websocket:
                state.active_websocket = None


def run() -> None:
    uvicorn.run(
        "bridge:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    run()
