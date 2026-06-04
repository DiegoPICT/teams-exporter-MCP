# teams-chat-gw-bridge-mcp

Local WebSocket bridge for Teams Chat Exporter and upcoming MCP adapter integration.

This repository contains a working Phase 1 bridge plus initial Phase 2 protocol skeleton handlers.

## Current Status

- Phase 1 complete: extension can connect to a local bridge and complete `HELLO` -> `HELLO_ACK`.
- Phase 2 in progress: command router and placeholder handlers for `LIST_CONVERSATIONS`, `START_SNAPSHOT`, and `CANCEL` are implemented.
- Auto-reload enabled for local development (`python -m bridge`).
- Canonical logging is enabled to console and `log/bridge.log`.
- Canonical frame helper is in place for consistent protocol envelopes.

## Protocol Reference

- Bridge design: `WEBSOCKET_BRIDGE_MCP_DESIGN.md`
- Implementation plan and progress: `IMPLEMENTATION.md`
- Architecture plan: `DESIGN.md`

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies.
3. Run the bridge.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m bridge
```

Default endpoint:

- `ws://127.0.0.1:8765/ws`

## Configuration

Runtime settings are loaded from `.env`:

```env
BRIDGE_HOST=127.0.0.1
BRIDGE_PORT=8765
BRIDGE_PATH=/ws
```

## Logs

- File logs: `log/bridge.log`
- Console logs: standard output

Expected Phase 1 lifecycle events include:

- `event=bridge_started`
- `event=client_connected`
- `event=hello_received`
- `event=hello_ack_sent`
- `event=client_disconnected`

## Testing

Standalone local emulators are available:

- Extension emulator: `testing/emulate_extension.py`
- Consumer emulator: `testing/emulate_consumer.py`

Usage guide:

- `testing/README.md`

## Repository Layout

- `bridge.py`: FastAPI WebSocket server and Phase 1 session lifecycle
- `frame_helper.py`: canonical frame builder utilities
- `logging_helper.py`: logger setup (console + rotating file)
- `testing/`: local emulation scripts for extension and consumer behavior
- `IMPLEMENTATION.md`: phased delivery plan and status
- `DESIGN.md`: target architecture and data flow
- `WEBSOCKET_BRIDGE_MCP_DESIGN.md`: protocol-level contract and semantics

## Next Up (Phase 2)

- Add status/health HTTP endpoints (`/health`, `/bridge/status`)
- Expand placeholder handlers toward real extension data flow
- Add automated smoke test coverage for protocol paths
