import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from mcp_wrapper import __version__
from mcp_wrapper.config import McpConfig, load_config
from mcp_wrapper.state import BridgeStateStore, McpSession, SessionStore
from mcp_wrapper.supervisor import BridgeSupervisor
from mcp_wrapper.tools import build_tool_list, call_tool


logger = logging.getLogger("mcp_wrapper")
config: McpConfig = load_config()
sessions = SessionStore()
bridge_state = BridgeStateStore()
bridge_supervisor = BridgeSupervisor(config, bridge_state)


def _setup_logging() -> None:
    logger.setLevel(getattr(logging, config.log_level, logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def _jsonrpc_error(request_id: Any, code: int, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if data is not None:
        payload["error"]["data"] = data
    return payload


def _negotiate_version(requested: str) -> str:
    if requested in config.protocol_versions:
        return requested
    return config.protocol_versions[0]


def _validate_origin(request: Request) -> None:
    if not config.allow_local_origins_only:
        return

    origin = request.headers.get("origin")
    if origin is None:
        return

    allowed = {
        "http://127.0.0.1",
        "http://localhost",
        "https://127.0.0.1",
        "https://localhost",
    }
    if origin not in allowed:
        raise HTTPException(status_code=403, detail="Origin not allowed")


def _require_session(request: Request) -> McpSession:
    session_id = request.headers.get("Mcp-Session-Id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing Mcp-Session-Id header")

    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    version_header = request.headers.get("MCP-Protocol-Version")
    if version_header is None:
        raise HTTPException(status_code=400, detail="Missing MCP-Protocol-Version header")
    if version_header != session.protocol_version:
        raise HTTPException(status_code=400, detail="Unsupported MCP-Protocol-Version")

    return session


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    _setup_logging()
    logger.info(
        "event=mcp_wrapper_started host=%s port=%s path=%s versions=%s manage_bridge=%s",
        config.host,
        config.port,
        config.path,
        ",".join(config.protocol_versions),
        config.manage_bridge,
    )
    try:
        await bridge_supervisor.start()
        yield
    finally:
        await bridge_supervisor.stop()
        logger.info("event=mcp_wrapper_stopped")


app = FastAPI(title="Teams Chat Gateway MCP Wrapper", version=__version__, lifespan=lifespan)


@app.get("/{full_path:path}")
async def mcp_get(request: Request, full_path: str) -> Response:
    request_path = "/" + full_path
    if request_path != config.path:
        return PlainTextResponse("Not Found", status_code=404)

    _validate_origin(request)
    return PlainTextResponse("Method Not Allowed", status_code=405)


@app.post("/{full_path:path}")
async def mcp_post(request: Request, full_path: str) -> Response:
    request_path = "/" + full_path
    if request_path != config.path:
        return PlainTextResponse("Not Found", status_code=404)

    _validate_origin(request)

    try:
        message = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(_jsonrpc_error(None, -32700, "Parse error"), status_code=400)

    if not isinstance(message, dict):
        return JSONResponse(_jsonrpc_error(None, -32600, "Invalid Request"), status_code=400)

    jsonrpc = message.get("jsonrpc")
    method = message.get("method")
    request_id = message.get("id")

    if jsonrpc != "2.0":
        return JSONResponse(_jsonrpc_error(request_id, -32600, "Invalid Request"), status_code=400)

    is_request = method is not None and request_id is not None
    is_notification = method is not None and request_id is None
    is_response = method is None and "result" in message

    if is_response:
        return Response(status_code=202)

    if not (is_request or is_notification):
        return JSONResponse(_jsonrpc_error(request_id, -32600, "Invalid Request"), status_code=400)

    if method == "initialize":
        if not is_request:
            return JSONResponse(_jsonrpc_error(request_id, -32600, "Invalid Request"), status_code=400)
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        requested_version = params.get("protocolVersion") if isinstance(params.get("protocolVersion"), str) else ""
        if not requested_version:
            return JSONResponse(
                _jsonrpc_error(request_id, -32602, "Missing protocolVersion"),
                status_code=400,
            )

        negotiated = _negotiate_version(requested_version)
        session = sessions.create(negotiated)

        result = {
            "protocolVersion": negotiated,
            "capabilities": {
                "tools": {
                    "listChanged": False,
                },
                "logging": {},
            },
            "serverInfo": {
                "name": "teams-chat-gw-bridge-mcp",
                "title": "Teams Chat Gateway MCP Wrapper",
                "version": __version__,
            },
            "instructions": "Use tools/list to discover supported MCP tools.",
        }
        headers = {
            "Mcp-Session-Id": session.session_id,
        }
        return JSONResponse(_jsonrpc_result(request_id, result), headers=headers)

    try:
        session = _require_session(request)
    except HTTPException as exc:
        return PlainTextResponse(str(exc.detail), status_code=exc.status_code)

    if method == "notifications/initialized":
        sessions.set_initialized(session.session_id)
        return Response(status_code=202)

    if not session.initialized:
        return JSONResponse(
            _jsonrpc_error(request_id, -32002, "Server not initialized"),
            status_code=400,
        )

    if method == "notifications/cancelled":
        return Response(status_code=202)

    if method == "tools/list":
        result = {
            "tools": build_tool_list(),
        }
        return JSONResponse(_jsonrpc_result(request_id, result))

    if method == "tools/call":
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        tool_name = params.get("name")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else params.get("arguments")
        if not isinstance(tool_name, str) or not tool_name:
            return JSONResponse(
                _jsonrpc_error(request_id, -32602, "tools/call requires tool name"),
                status_code=400,
            )

        try:
            tool_result = call_tool(
                tool_name,
                arguments,
                protocol_version=session.protocol_version,
                bridge_snapshot_provider=bridge_supervisor.snapshot,
                bridge_base_url=config.bridge_base_url,
            )
        except KeyError:
            return JSONResponse(_jsonrpc_error(request_id, -32602, f"Unknown tool: {tool_name}"), status_code=400)
        except ValueError as exc:
            return JSONResponse(_jsonrpc_error(request_id, -32602, str(exc)), status_code=400)

        return JSONResponse(_jsonrpc_result(request_id, tool_result))

    if method == "logging/setLevel":
        return JSONResponse(_jsonrpc_result(request_id, {}))

    if is_notification:
        return Response(status_code=202)

    return JSONResponse(_jsonrpc_error(request_id, -32601, f"Method not found: {method}"), status_code=404)


def run() -> None:
    uvicorn.run(
        "mcp_wrapper.server:app",
        host=config.host,
        port=config.port,
        reload=False,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    run()
