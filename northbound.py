import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from logging_helper import get_logger
from service import BridgeService, BridgeServiceError


router = APIRouter()
service: BridgeService | None = None
logger = get_logger(__name__)


def configure_router(bridge_service: BridgeService) -> APIRouter:
    global service
    service = bridge_service
    return router


def get_service() -> BridgeService:
    if service is None:
        raise RuntimeError("Bridge service is not configured")
    return service


def as_http_error(exc: BridgeServiceError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail={"code": exc.code, "message": exc.message})


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True}


@router.get("/bridge/status")
async def bridge_status() -> dict[str, Any]:
    bridge_service = get_service()
    async with bridge_service.lock:
        return bridge_service.build_status_payload()


@router.get("/conversations")
async def list_conversations(request: Request) -> dict[str, Any]:
    bridge_service = get_service()
    logger.info("event=http_request_received route=/conversations method=GET client=%s", request.client.host if request.client else "unknown")
    try:
        payload = await bridge_service.list_conversations()
        logger.info("event=http_request_completed route=/conversations status=200")
        return payload
    except BridgeServiceError as exc:
        logger.warning("event=http_request_failed route=/conversations status=%s code=%s message=%s", exc.http_status, exc.code, exc.message)
        raise as_http_error(exc) from exc


@router.post("/snapshots")
async def start_snapshot(request: Request, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    bridge_service = get_service()
    logger.info("event=http_request_received route=/snapshots method=POST client=%s", request.client.host if request.client else "unknown")
    try:
        request_id = await bridge_service.start_snapshot(payload or {})
        logger.info("event=http_request_completed route=/snapshots status=200 request_id=%s", request_id)
        return {"requestId": request_id, "events": f"/snapshots/{request_id}/events"}
    except BridgeServiceError as exc:
        logger.warning("event=http_request_failed route=/snapshots status=%s code=%s message=%s", exc.http_status, exc.code, exc.message)
        raise as_http_error(exc) from exc


@router.post("/snapshots/{request_id}/cancel")
async def cancel_snapshot(request: Request, request_id: str) -> dict[str, Any]:
    bridge_service = get_service()
    logger.info("event=http_request_received route=/snapshots/cancel method=POST request_id=%s client=%s", request_id, request.client.host if request.client else "unknown")
    try:
        result = await bridge_service.cancel(request_id)
        logger.info("event=http_request_completed route=/snapshots/cancel status=200 request_id=%s", request_id)
        return result
    except BridgeServiceError as exc:
        logger.warning("event=http_request_failed route=/snapshots/cancel status=%s code=%s message=%s", exc.http_status, exc.code, exc.message)
        raise as_http_error(exc) from exc


@router.get("/snapshots/{request_id}/events")
async def snapshot_events(request: Request, request_id: str) -> StreamingResponse:
    bridge_service = get_service()
    logger.info("event=http_request_received route=/snapshots/events method=GET request_id=%s client=%s", request_id, request.client.host if request.client else "unknown")
    try:
        snapshot_operation = await bridge_service.get_snapshot_operation(request_id)
    except BridgeServiceError as exc:
        logger.warning("event=http_request_failed route=/snapshots/events status=%s code=%s message=%s", exc.http_status, exc.code, exc.message)
        raise as_http_error(exc) from exc

    async def event_stream() -> Any:
        index = 0
        keepalive_tick = 0
        try:
            while True:
                if await request.is_disconnected():
                    logger.info("event=northbound_sse_client_disconnected request_id=%s", request_id)
                    break
                event = await snapshot_operation.get_event(index)
                if event is None:
                    if await snapshot_operation.is_terminal():
                        break
                    await asyncio.sleep(0.2)
                    keepalive_tick += 1
                    if keepalive_tick >= 25:
                        yield ": keepalive\n\n"
                        keepalive_tick = 0
                    continue

                keepalive_tick = 0
                index += 1
                event_type = event.get("type")
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(event)}\n\n"

                if event_type in {"DONE", "ERROR"}:
                    break
            logger.info("event=http_request_completed route=/snapshots/events status=200 request_id=%s", request_id)
        except Exception as exc:
            logger.exception("event=northbound_sse_error request_id=%s error=%s", request_id, str(exc))

    return StreamingResponse(event_stream(), media_type="text/event-stream")
