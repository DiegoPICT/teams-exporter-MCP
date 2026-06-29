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

from frame_helper import PROTOCOL_VERSION, make_frame
from logging_helper import get_log_file_path, get_logger, setup_canonical_logging
from northbound import configure_router
from service import BridgeService, BridgeServiceError
from southbound import ExtensionSession


load_dotenv()


HOST = os.getenv("BRIDGE_HOST", "127.0.0.1")
PORT = int(os.getenv("BRIDGE_PORT", "8765"))
WS_PATH = os.getenv("BRIDGE_PATH", "/ws")

logger = get_logger(__name__)
service = BridgeService()


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


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_canonical_logging("teams_bridge")
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
        async with service.lock:
            session = service.extension_session
        if session is not None:
            await session.close(code=1001, reason="Server shutting down")
        await service.unregister_extension("Server shutting down")
        logger.info("event=bridge_stopped")


app = FastAPI(title="Teams Chat Exporter MCP Bridge", version="0.3.0", lifespan=lifespan)
app.include_router(configure_router(service))


@app.websocket("/{full_path:path}")
async def extension_websocket(websocket: WebSocket, full_path: str) -> None:
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

    await websocket.accept()
    session = ExtensionSession(websocket)

    try:
        await service.register_extension(session)
    except BridgeServiceError:
        await session.close(code=1013, reason="Another extension session is active")
        logger.warning("event=connection_rejected_busy client=%s", client)
        return

    logger.info("event=southbound_client_connected client=%s", client)

    try:
        raw = await websocket.receive_text()
        hello_frame = parse_json_message(raw)
        validate_hello(hello_frame)
        await service.set_session_info(hello_frame)

        payload = hello_frame.get("payload") if isinstance(hello_frame.get("payload"), dict) else {}
        conv_title = payload.get("conversationTitle", "")
        
        logger.info(
            "event=hello_received session_id=%s tab_id=%s conversation_id=%s conversation_title_length=%d",
            hello_frame.get("sessionId"),
            payload.get("tabId"),
            payload.get("conversationId"),
            len(conv_title) if conv_title else 0,
        )
        logger.debug(
            "event=hello_received_data conversation_title=%s",
            conv_title
        )

        await session.send_frame(make_frame("HELLO_ACK"))
        logger.info("event=hello_ack_sent")

        while True:
            try:
                raw_message = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
            except asyncio.TimeoutError:
                logger.info("event=idle_timeout_sending_ping client=%s", client)
                try:
                    await session.send_frame(make_frame("PING"))
                except Exception as exc:
                    logger.error("event=failed_to_send_ping client=%s error=%s", client, str(exc))
                    break
                continue

            try:
                frame = parse_json_message(raw_message)
            except ValueError as exc:
                logger.warning("event=invalid_frame client=%s error=%s", client, str(exc))
                await session.send_frame(make_frame("ERROR", payload={"code": "UNSUPPORTED"}, error=str(exc)))
                continue

            frame_type = frame.get("type")

            if frame_type == "PING":
                logger.info("event=ping_received client=%s", client)
                await session.send_frame(make_frame("PONG", request_id=frame.get("requestId")))
                continue

            if frame_type == "PONG":
                logger.info("event=pong_received client=%s", client)
                continue

            await service.handle_extension_frame(frame)

    except WebSocketDisconnect as exc:
        logger.info("event=southbound_client_disconnected client=%s code=%s", client, exc.code)
    except ValueError as exc:
        logger.error("event=protocol_error client=%s error=%s", client, str(exc))
        with suppress(Exception):
            await websocket.close(code=1002, reason=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.exception("event=unexpected_error client=%s error=%s", client, str(exc))
        with suppress(Exception):
            await websocket.close(code=1011, reason="Internal server error")
    finally:
        await service.unregister_extension("Extension disconnected")


def run() -> None:
    log_level = os.getenv("BRIDGE_LOG_LEVEL", "INFO").lower()
    uvicorn.run(
        "bridge:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level=log_level,
    )


if __name__ == "__main__":
    run()
