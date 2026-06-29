import os
import shlex
import sys
from dataclasses import dataclass


DEFAULT_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26")


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_versions(raw: str | None) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return DEFAULT_PROTOCOL_VERSIONS
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    return values or DEFAULT_PROTOCOL_VERSIONS


@dataclass(frozen=True)
class McpConfig:
    host: str
    port: int
    path: str
    log_level: str
    protocol_versions: tuple[str, ...]
    allow_local_origins_only: bool
    bridge_base_url: str
    manage_bridge: bool
    bridge_command: tuple[str, ...]
    bridge_startup_timeout_seconds: float
    bridge_shutdown_timeout_seconds: float
    bridge_monitor_interval_seconds: float
    bridge_auto_restart: bool


def _default_bridge_command() -> tuple[str, ...]:
    return (
        sys.executable,
        "-m",
        "uvicorn",
        "bridge:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
        "--log-level",
        "info",
    )


def _parse_command(raw: str | None) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return _default_bridge_command()
    parts = tuple(shlex.split(raw))
    if not parts:
        return _default_bridge_command()
    return parts


def load_config() -> McpConfig:
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8766"))
    path = os.getenv("MCP_PATH", "/mcp")
    log_level = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
    protocol_versions = _parse_versions(os.getenv("MCP_PROTOCOL_VERSIONS"))
    allow_local_origins_only = _parse_bool(os.getenv("MCP_LOCAL_ORIGINS_ONLY"), default=True)
    bridge_base_url = os.getenv("MCP_BRIDGE_BASE_URL", "http://127.0.0.1:8765")
    manage_bridge = _parse_bool(os.getenv("MCP_MANAGE_BRIDGE"), default=True)
    bridge_command = _parse_command(os.getenv("MCP_BRIDGE_COMMAND"))
    bridge_startup_timeout_seconds = float(os.getenv("MCP_BRIDGE_STARTUP_TIMEOUT_SECONDS", "20"))
    bridge_shutdown_timeout_seconds = float(os.getenv("MCP_BRIDGE_SHUTDOWN_TIMEOUT_SECONDS", "8"))
    bridge_monitor_interval_seconds = float(os.getenv("MCP_BRIDGE_MONITOR_INTERVAL_SECONDS", "2"))
    bridge_auto_restart = _parse_bool(os.getenv("MCP_BRIDGE_AUTO_RESTART"), default=True)

    if not path.startswith("/"):
        raise ValueError("MCP_PATH must start with '/'")
    if not protocol_versions:
        raise ValueError("At least one MCP protocol version must be configured")

    return McpConfig(
        host=host,
        port=port,
        path=path,
        log_level=log_level,
        protocol_versions=protocol_versions,
        allow_local_origins_only=allow_local_origins_only,
        bridge_base_url=bridge_base_url,
        manage_bridge=manage_bridge,
        bridge_command=bridge_command,
        bridge_startup_timeout_seconds=bridge_startup_timeout_seconds,
        bridge_shutdown_timeout_seconds=bridge_shutdown_timeout_seconds,
        bridge_monitor_interval_seconds=bridge_monitor_interval_seconds,
        bridge_auto_restart=bridge_auto_restart,
    )
