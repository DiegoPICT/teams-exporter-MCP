import time
from typing import Any


PROTOCOL_VERSION = "teams-exporter-bridge/v1"


def now_ms() -> int:
    return int(time.time() * 1000)


def make_frame(
    frame_type: str,
    *,
    request_id: str | None = None,
    payload: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    frame: dict[str, Any] = {
        "v": PROTOCOL_VERSION,
        "type": frame_type,
        "ts": now_ms(),
    }

    if request_id is not None:
        frame["requestId"] = request_id

    if payload is not None:
        frame["payload"] = payload

    if error is not None:
        frame["error"] = error

    return frame


def make_error(
    *,
    request_id: str | None,
    code: str,
    error: str,
) -> dict[str, Any]:
    return make_frame(
        "ERROR",
        request_id=request_id,
        payload={"code": code},
        error=error,
    )
