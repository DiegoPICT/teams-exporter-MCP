import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any


SMOKE_TOOL_NAME = "wrapper_status"
SNAPSHOT_CURRENT_CHAT_TOOL_NAME = "snapshot_current_chat"


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 10.0) -> tuple[int, dict[str, Any]]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            if isinstance(parsed, dict):
                return response.status, parsed
            return response.status, {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        if isinstance(parsed, dict):
            return exc.code, parsed
        return exc.code, {}


def _extract_text(message: dict[str, Any]) -> str:
    for key in ("text", "content", "body"):
        value = message.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _extract_author(message: dict[str, Any]) -> str:
    for key in ("author", "from", "sender"):
        value = message.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _extract_timestamp(message: dict[str, Any]) -> str:
    for key in ("ts", "timestamp", "createdDateTime"):
        value = message.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _message_summary(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "author": _extract_author(message),
        "timestamp": _extract_timestamp(message),
        "text": _extract_text(message),
        "raw": message,
    }


def _snapshot_current_chat(bridge_base_url: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    args = arguments or {}
    if not isinstance(args, dict):
        return {
            "content": [{"type": "text", "text": "snapshot_current_chat arguments must be an object."}],
            "structuredContent": {"ok": False, "code": "INVALID_ARGUMENTS"},
            "isError": True,
        }

    payload: dict[str, Any] = {
        "includeReplies": bool(args.get("includeReplies", True)),
        "includeReactions": bool(args.get("includeReactions", True)),
        "includeSystem": bool(args.get("includeSystem", False)),
    }
    if isinstance(args.get("startAt"), str):
        payload["startAt"] = args["startAt"]
    if isinstance(args.get("endAt"), str):
        payload["endAt"] = args["endAt"]

    timeout_value = args.get("timeoutSeconds", 60.0)
    timeout_seconds = float(timeout_value) if isinstance(timeout_value, (int, float)) else 60.0
    if timeout_seconds < 5:
        timeout_seconds = 5

    status, start_body = _request_json("POST", f"{bridge_base_url.rstrip('/')}/snapshots", payload=payload, timeout=10.0)
    if status != 200:
        detail = start_body.get("detail") if isinstance(start_body.get("detail"), dict) else {}
        code = detail.get("code", "BRIDGE_ERROR")
        message = detail.get("message", "Failed to start snapshot")
        return {
            "content": [{"type": "text", "text": f"snapshot_current_chat failed: [{code}] {message}"}],
            "structuredContent": {
                "ok": False,
                "code": code,
                "message": message,
                "status": status,
                "raw": start_body,
            },
            "isError": True,
        }

    request_id = start_body.get("requestId")
    if not isinstance(request_id, str):
        return {
            "content": [{"type": "text", "text": "snapshot_current_chat failed: missing requestId"}],
            "structuredContent": {"ok": False, "code": "INVALID_RESPONSE", "raw": start_body},
            "isError": True,
        }

    events_url = f"{bridge_base_url.rstrip('/')}/snapshots/{urllib.parse.quote(request_id)}/events"
    req = urllib.request.Request(events_url, method="GET", headers={"Accept": "text/event-stream"})

    first_message: dict[str, Any] | None = None
    last_message: dict[str, Any] | None = None
    message_count = 0
    status_text = "done"
    terminal: dict[str, Any] | None = None
    started_payload: dict[str, Any] | None = None

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data: "):
                    continue

                frame = json.loads(line[len("data: ") :])
                if not isinstance(frame, dict):
                    continue

                frame_type = frame.get("type")
                payload_obj = frame.get("payload") if isinstance(frame.get("payload"), dict) else {}

                if frame_type == "SNAPSHOT_STARTED":
                    started_payload = payload_obj
                elif frame_type == "CHUNK":
                    messages = payload_obj.get("messages") if isinstance(payload_obj.get("messages"), list) else []
                    for item in messages:
                        if not isinstance(item, dict):
                            continue
                        message_count += 1
                        if first_message is None:
                            first_message = _message_summary(item)
                        last_message = _message_summary(item)
                elif frame_type == "ERROR":
                    status_text = "error"
                    terminal = frame
                    break
                elif frame_type == "DONE":
                    done_payload = payload_obj
                    if done_payload.get("cancelled") is True:
                        status_text = "cancelled"
                    terminal = frame
                    break
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        return {
            "content": [{"type": "text", "text": f"snapshot_current_chat timed out or failed while streaming events: {exc}"}],
            "structuredContent": {
                "ok": False,
                "code": "STREAM_ERROR",
                "message": str(exc),
                "requestId": request_id,
            },
            "isError": True,
        }

    structured = {
        "ok": status_text != "error",
        "requestId": request_id,
        "status": status_text,
        "messageCount": message_count,
        "firstMessage": first_message,
        "lastMessage": last_message,
        "conversationId": started_payload.get("conversationId") if isinstance(started_payload, dict) else None,
        "conversationTitle": started_payload.get("conversationTitle") if isinstance(started_payload, dict) else None,
        "rawTerminal": terminal,
    }

    summary_text = (
        f"snapshot_current_chat finished with status={status_text}, messageCount={message_count}."
    )
    if message_count > 0 and first_message is not None and last_message is not None:
        summary_text += (
            f" First: [{first_message.get('timestamp')}] {first_message.get('author')}: {first_message.get('text')[:120]}"
            f" | Last: [{last_message.get('timestamp')}] {last_message.get('author')}: {last_message.get('text')[:120]}"
        )

    return {
        "content": [{"type": "text", "text": summary_text}],
        "structuredContent": structured,
        "isError": status_text == "error",
    }


def build_tool_list() -> list[dict[str, Any]]:
    return [
        {
            "name": SMOKE_TOOL_NAME,
            "title": "Wrapper Status",
            "description": "Returns MCP wrapper runtime status and negotiated protocol version.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "server": {"type": "string"},
                    "protocolVersion": {"type": "string"},
                    "bridge": {"type": "object"},
                },
                "required": ["ok", "server", "protocolVersion", "bridge"],
                "additionalProperties": False,
            },
        },
        {
            "name": SNAPSHOT_CURRENT_CHAT_TOOL_NAME,
            "title": "Snapshot Current Chat",
            "description": "Starts a snapshot for the currently selected Teams chat and returns first/last messages.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "startAt": {"type": "string"},
                    "endAt": {"type": "string"},
                    "includeReplies": {"type": "boolean"},
                    "includeReactions": {"type": "boolean"},
                    "includeSystem": {"type": "boolean"},
                    "timeoutSeconds": {"type": "number", "minimum": 5, "maximum": 300},
                },
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "requestId": {"type": "string"},
                    "status": {"type": "string"},
                    "messageCount": {"type": "integer"},
                    "firstMessage": {"type": ["object", "null"]},
                    "lastMessage": {"type": ["object", "null"]},
                    "conversationId": {"type": ["string", "null"]},
                    "conversationTitle": {"type": ["string", "null"]},
                    "rawTerminal": {"type": ["object", "null"]},
                },
                "required": ["ok", "requestId", "status", "messageCount", "firstMessage", "lastMessage"],
                "additionalProperties": True,
            },
        },
    ]


def call_tool(
    name: str,
    arguments: dict[str, Any] | None,
    *,
    protocol_version: str,
    bridge_snapshot_provider: Callable[[], dict[str, Any]],
    bridge_base_url: str,
) -> dict[str, Any]:
    if name == SMOKE_TOOL_NAME:
        if arguments not in (None, {}):
            raise ValueError("wrapper_status does not accept arguments")

        structured = {
            "ok": True,
            "server": "teams-chat-gw-bridge-mcp",
            "protocolVersion": protocol_version,
            "bridge": bridge_snapshot_provider(),
        }
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"MCP wrapper is ready (protocol={protocol_version}).",
                }
            ],
            "structuredContent": structured,
            "isError": False,
        }

    if name == SNAPSHOT_CURRENT_CHAT_TOOL_NAME:
        return _snapshot_current_chat(bridge_base_url=bridge_base_url, arguments=arguments)

    raise KeyError(name)
