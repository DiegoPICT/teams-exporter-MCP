import time
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class McpSession:
    session_id: str
    protocol_version: str
    initialized: bool
    created_at: float


@dataclass
class BridgeRuntimeState:
    process_state: str
    connectivity: str
    has_process: bool
    process_id: int | None
    restart_count: int
    last_exit_code: int | None
    last_error: str | None
    last_transition_at: float


class BridgeStateStore:
    def __init__(self) -> None:
        now = time.time()
        self._state = BridgeRuntimeState(
            process_state="NOT_STARTED",
            connectivity="UNKNOWN",
            has_process=False,
            process_id=None,
            restart_count=0,
            last_exit_code=None,
            last_error=None,
            last_transition_at=now,
        )

    def _touch(self) -> None:
        self._state.last_transition_at = time.time()

    def mark_attached(self) -> None:
        self._state.process_state = "ATTACHED"
        self._state.connectivity = "REACHABLE"
        self._state.has_process = False
        self._state.process_id = None
        self._state.last_error = None
        self._touch()

    def mark_starting(self) -> None:
        self._state.process_state = "STARTING"
        self._state.connectivity = "UNKNOWN"
        self._state.last_error = None
        self._touch()

    def mark_running(self, pid: int | None, *, started_by_wrapper: bool) -> None:
        self._state.process_state = "RUNNING" if started_by_wrapper else "ATTACHED"
        self._state.connectivity = "REACHABLE"
        self._state.has_process = started_by_wrapper
        self._state.process_id = pid if started_by_wrapper else None
        self._state.last_error = None
        self._touch()

    def mark_unreachable(self, reason: str) -> None:
        self._state.connectivity = "UNREACHABLE"
        self._state.last_error = reason
        self._touch()

    def mark_crashed(self, exit_code: int | None) -> None:
        self._state.process_state = "CRASHED"
        self._state.connectivity = "UNREACHABLE"
        self._state.has_process = False
        self._state.process_id = None
        self._state.last_exit_code = exit_code
        self._touch()

    def mark_stopped(self) -> None:
        self._state.process_state = "STOPPED"
        self._state.connectivity = "UNREACHABLE"
        self._state.has_process = False
        self._state.process_id = None
        self._touch()

    def increment_restart(self) -> None:
        self._state.restart_count += 1
        self._touch()

    def snapshot(self) -> dict[str, Any]:
        return {
            "processState": self._state.process_state,
            "connectivity": self._state.connectivity,
            "hasProcess": self._state.has_process,
            "processId": self._state.process_id,
            "restartCount": self._state.restart_count,
            "lastExitCode": self._state.last_exit_code,
            "lastError": self._state.last_error,
            "lastTransitionAt": self._state.last_transition_at,
        }


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, McpSession] = {}

    def create(self, protocol_version: str) -> McpSession:
        session = McpSession(
            session_id=uuid.uuid4().hex,
            protocol_version=protocol_version,
            initialized=False,
            created_at=time.time(),
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> McpSession | None:
        return self._sessions.get(session_id)

    def set_initialized(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.initialized = True
