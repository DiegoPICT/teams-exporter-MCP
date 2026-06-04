import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from service import BridgeService, BridgeServiceError


router = APIRouter()
service: BridgeService | None = None


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
async def list_conversations() -> dict[str, Any]:
    bridge_service = get_service()
    try:
        payload = await bridge_service.list_conversations()
        return payload
    except BridgeServiceError as exc:
        raise as_http_error(exc) from exc


@router.post("/snapshots")
async def start_snapshot(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    bridge_service = get_service()
    try:
        request_id = await bridge_service.start_snapshot(payload or {})
        return {"requestId": request_id, "events": f"/snapshots/{request_id}/events"}
    except BridgeServiceError as exc:
        raise as_http_error(exc) from exc


@router.post("/snapshots/{request_id}/cancel")
async def cancel_snapshot(request_id: str) -> dict[str, Any]:
    bridge_service = get_service()
    try:
        return await bridge_service.cancel(request_id)
    except BridgeServiceError as exc:
        raise as_http_error(exc) from exc


@router.get("/snapshots/{request_id}/events")
async def snapshot_events(request_id: str) -> StreamingResponse:
    bridge_service = get_service()
    try:
        snapshot_operation = await bridge_service.get_snapshot_operation(request_id)
    except BridgeServiceError as exc:
        raise as_http_error(exc) from exc

    async def event_stream() -> Any:
        index = 0
        keepalive_tick = 0
        while True:
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

    return StreamingResponse(event_stream(), media_type="text/event-stream")
