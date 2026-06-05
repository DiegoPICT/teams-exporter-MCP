import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any

from frame_helper import make_error, make_frame
from logging_helper import get_logger
from southbound import ExtensionSession


STATE_CONNECTED_IDLE = "CONNECTED_IDLE"
STATE_BUSY = "BUSY"
STATE_CONTEXT_LOST = "CONTEXT_LOST"
STATE_DISCONNECTED = "DISCONNECTED"
STATE_ERROR = "ERROR"

LIST_CONVERSATIONS = "LIST_CONVERSATIONS"
START_SNAPSHOT = "START_SNAPSHOT"
CANCEL = "CANCEL"

ERROR_FRAME = "ERROR"
CONVERSATIONS = "CONVERSATIONS"
SNAPSHOT_STARTED = "SNAPSHOT_STARTED"
CHUNK = "CHUNK"
DONE = "DONE"

TERMINAL_TYPES = {DONE, ERROR_FRAME}
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("BRIDGE_OPERATION_TIMEOUT", "30"))

logger = get_logger(__name__)


class BridgeServiceError(Exception):
    def __init__(self, message: str, *, code: str, http_status: int) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status


@dataclass
class ListOperation:
    request_id: str
    result_future: asyncio.Future[dict]


class SnapshotOperation:
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        self.events: list[dict[str, Any]] = []
        self.terminal = False
        self._lock = asyncio.Lock()

    async def publish(self, frame: dict[str, Any]) -> None:
        async with self._lock:
            if self.terminal:
                return
            self.events.append(frame)
            if frame.get("type") in TERMINAL_TYPES:
                self.terminal = True

    async def get_event(self, index: int) -> dict[str, Any] | None:
        async with self._lock:
            if index < len(self.events):
                return self.events[index]
            return None

    async def is_terminal(self) -> bool:
        async with self._lock:
            return self.terminal


class BridgeService:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.extension_session: ExtensionSession | None = None
        self.connection_state = STATE_DISCONNECTED
        self.last_error: str | None = None
        self.session_info: dict[str, Any] = {}

        self.active_operation_type: str | None = None
        self.active_operation_request_id: str | None = None
        self.active_list_operation: ListOperation | None = None
        self.active_snapshot_operation: SnapshotOperation | None = None
        self.snapshot_history: dict[str, SnapshotOperation] = {}

    def _set_state(self, state: str, error: str | None = None) -> None:
        self.connection_state = state
        self.last_error = error

    def _set_active_operation(self, op_type: str, request_id: str) -> None:
        self.active_operation_type = op_type
        self.active_operation_request_id = request_id
        self._set_state(STATE_BUSY)

    def _clear_active_operation(self) -> None:
        self.active_operation_type = None
        self.active_operation_request_id = None
        if self.extension_session is None:
            self._set_state(STATE_DISCONNECTED)
        elif self.connection_state == STATE_CONTEXT_LOST:
            self._set_state(STATE_CONTEXT_LOST, self.last_error)
        else:
            self._set_state(STATE_CONNECTED_IDLE)

    def build_status_payload(self) -> dict[str, Any]:
        return {
            "connectionState": self.connection_state,
            "activeOperation": {
                "type": self.active_operation_type,
                "requestId": self.active_operation_request_id,
            },
            "session": self.session_info,
            "lastError": self.last_error,
            "hasActiveSocket": self.extension_session is not None,
        }

    async def register_extension(self, session: ExtensionSession) -> None:
        async with self.lock:
            if self.extension_session is not None:
                raise BridgeServiceError(
                    "Another extension session is active",
                    code="BUSY",
                    http_status=409,
                )
            self.extension_session = session
            self._set_state(STATE_CONNECTED_IDLE)

    async def set_session_info(self, hello_frame: dict[str, Any]) -> None:
        payload = hello_frame.get("payload") if isinstance(hello_frame.get("payload"), dict) else {}
        async with self.lock:
            self.session_info = {
                "sessionId": hello_frame.get("sessionId"),
                "tabId": payload.get("tabId"),
                "conversationId": payload.get("conversationId"),
                "conversationTitle": payload.get("conversationTitle"),
            }

    async def unregister_extension(self, reason: str) -> None:
        async with self.lock:
            self.extension_session = None
            self.session_info = {}
            self._set_state(STATE_DISCONNECTED, reason)

            if self.active_list_operation is not None and not self.active_list_operation.result_future.done():
                self.active_list_operation.result_future.set_exception(
                    BridgeServiceError(
                        "Extension disconnected while waiting for list response",
                        code="DISCONNECTED",
                        http_status=503,
                    )
                )

            if self.active_snapshot_operation is not None and not self.active_snapshot_operation.terminal:
                error_frame = make_error(
                    request_id=self.active_snapshot_operation.request_id,
                    code="DISCONNECTED",
                    error="Extension disconnected during snapshot",
                )
                await self.active_snapshot_operation.publish(error_frame)

            self.active_list_operation = None
            self.active_snapshot_operation = None
            self._clear_active_operation()

    async def ensure_command_ready(self) -> ExtensionSession:
        async with self.lock:
            if self.extension_session is None:
                raise BridgeServiceError(
                    "Extension is not connected",
                    code="DISCONNECTED",
                    http_status=503,
                )
            if self.connection_state == STATE_CONTEXT_LOST:
                raise BridgeServiceError(
                    "Extension context is lost; reconnect required",
                    code="CONTEXT_LOST",
                    http_status=409,
                )
            return self.extension_session

    async def list_conversations(self) -> dict[str, Any]:
        session = await self.ensure_command_ready()
        request_id = f"list-{uuid.uuid4().hex[:10]}"

        async with self.lock:
            if self.active_operation_type is not None:
                raise BridgeServiceError(
                    "Another operation is already running",
                    code="BUSY",
                    http_status=409,
                )
            list_operation = ListOperation(request_id=request_id, result_future=asyncio.get_running_loop().create_future())
            self.active_list_operation = list_operation
            self._set_active_operation(LIST_CONVERSATIONS, request_id)

        outbound = make_frame(LIST_CONVERSATIONS, request_id=request_id)
        await session.send_frame(outbound)
        logger.info("event=command_sent type=%s request_id=%s", LIST_CONVERSATIONS, request_id)

        try:
            result = await asyncio.wait_for(list_operation.result_future, timeout=DEFAULT_TIMEOUT_SECONDS)
            return result
        except asyncio.TimeoutError as exc:
            async with self.lock:
                if self.active_list_operation is list_operation:
                    self.active_list_operation = None
                    self._clear_active_operation()
            raise BridgeServiceError(
                "Timed out waiting for CONVERSATIONS response",
                code="TIMEOUT",
                http_status=504,
            ) from exc

    async def start_snapshot(self, payload: dict[str, Any]) -> str:
        session = await self.ensure_command_ready()
        request_id = f"snap-{uuid.uuid4().hex[:10]}"

        async with self.lock:
            if self.active_operation_type is not None:
                raise BridgeServiceError(
                    "Another operation is already running",
                    code="BUSY",
                    http_status=409,
                )
            snapshot = SnapshotOperation(request_id=request_id)
            self.active_snapshot_operation = snapshot
            self.snapshot_history[request_id] = snapshot
            self._set_active_operation(START_SNAPSHOT, request_id)

        outbound = make_frame(START_SNAPSHOT, request_id=request_id, payload=payload if payload else None)
        await session.send_frame(outbound)
        logger.info("event=command_sent type=%s request_id=%s", START_SNAPSHOT, request_id)
        return request_id

    async def get_snapshot_operation(self, request_id: str) -> SnapshotOperation:
        async with self.lock:
            snapshot = self.snapshot_history.get(request_id)
            if snapshot is None:
                raise BridgeServiceError(
                    f"Snapshot operation not found: {request_id}",
                    code="NOT_FOUND",
                    http_status=404,
                )
            return snapshot

    async def cancel(self, request_id: str) -> dict[str, Any]:
        session = await self.ensure_command_ready()

        async with self.lock:
            active_snapshot = self.active_snapshot_operation
            active_request_id = self.active_operation_request_id

        if active_snapshot is None or active_request_id is None:
            done = make_frame(
                DONE,
                request_id=request_id,
                payload={"cancelled": True, "reason": "cancelled"},
            )
            return done

        if request_id != active_request_id:
            raise BridgeServiceError(
                f"CANCEL requestId {request_id} does not match active snapshot {active_request_id}",
                code="UNSUPPORTED",
                http_status=400,
            )

        outbound = make_frame(CANCEL, request_id=request_id)
        await session.send_frame(outbound)
        logger.info("event=command_sent type=%s request_id=%s", CANCEL, request_id)
        return {"requestId": request_id, "status": "sent"}

    async def handle_extension_frame(self, frame: dict[str, Any]) -> None:
        frame_type = frame.get("type")
        request_id = frame.get("requestId")
        logger.info("event=extension_frame_received type=%s request_id=%s", frame_type, request_id)

        async with self.lock:
            if frame_type == CONVERSATIONS:
                await self._handle_conversations_locked(frame)
                return
            if frame_type in {SNAPSHOT_STARTED, CHUNK, DONE, ERROR_FRAME}:
                await self._handle_snapshot_or_error_locked(frame)
                return

            logger.warning(
                "event=extension_frame_unhandled type=%s request_id=%s",
                frame_type,
                request_id,
            )

    async def _handle_conversations_locked(self, frame: dict[str, Any]) -> None:
        request_id = frame.get("requestId")
        if not isinstance(request_id, str):
            logger.warning("event=conversations_missing_request_id")
            return

        list_op = self.active_list_operation
        if list_op is None or list_op.request_id != request_id:
            logger.warning("event=conversations_request_mismatch request_id=%s", request_id)
            return

        payload = frame.get("payload") if isinstance(frame.get("payload"), dict) else {}
        if not list_op.result_future.done():
            list_op.result_future.set_result(payload)

        self.active_list_operation = None
        self._clear_active_operation()

    async def _handle_snapshot_or_error_locked(self, frame: dict[str, Any]) -> None:
        frame_type = frame.get("type")
        request_id = frame.get("requestId")

        if frame_type == ERROR_FRAME:
            payload = frame.get("payload") if isinstance(frame.get("payload"), dict) else {}
            error_code = payload.get("code", "UNKNOWN")
            error_message = frame.get("error", "Unknown error")
            
            logger.error("event=extension_operation_error request_id=%s code=%s message=%s", request_id, error_code, error_message)

            if error_code == "CONTEXT_LOST":
                self._set_state(STATE_CONTEXT_LOST, error_message if isinstance(error_message, str) else "CONTEXT_LOST")

            if self.active_list_operation is not None and self.active_list_operation.request_id == request_id:
                if not self.active_list_operation.result_future.done():
                    self.active_list_operation.result_future.set_exception(
                        BridgeServiceError(
                            error_message if isinstance(error_message, str) else "List operation failed",
                            code=error_code if isinstance(error_code, str) else "ERROR",
                            http_status=409 if error_code == "BUSY" else 500,
                        )
                    )
                self.active_list_operation = None
                self._clear_active_operation()
                return

        snapshot = self.active_snapshot_operation
        if snapshot is None:
            logger.warning("event=snapshot_frame_without_active_operation type=%s request_id=%s", frame_type, request_id)
            return

        if request_id != snapshot.request_id:
            logger.warning(
                "event=snapshot_request_mismatch type=%s request_id=%s expected_request_id=%s",
                frame_type,
                request_id,
                snapshot.request_id,
            )
            return

        await snapshot.publish(frame)

        if frame_type in TERMINAL_TYPES:
            self.active_snapshot_operation = None
            self._clear_active_operation()
