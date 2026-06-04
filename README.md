# teams-chat-gw-bridge-mcp

Local WebSocket bridge for Teams Chat Exporter and upcoming MCP adapter integration.

This repository currently contains a working Phase 1 bridge implementation and the protocol/design docs for planned Phase 2+ work.

## Current Status

- Phase 1 complete: extension can connect to a local bridge and complete `HELLO` -> `HELLO_ACK`.
- Auto-reload enabled for local development (`python -m bridge`).
- Canonical logging is enabled to console and `log/bridge.log`.
- Canonical frame helper is in place for consistent protocol envelopes.

## Protocol Reference

- Bridge design: `WEBSOCKET_BRIDGE_MCP_DESIGN.md`
- Implementation plan and progress: `IMPLEMENTATION.md`

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

## Repository Layout

- `bridge.py`: FastAPI WebSocket server and Phase 1 session lifecycle
- `frame_helper.py`: canonical frame builder utilities
- `logging_helper.py`: logger setup (console + rotating file)
- `IMPLEMENTATION.md`: phased delivery plan and status
- `WEBSOCKET_BRIDGE_MCP_DESIGN.md`: protocol-level contract and semantics

## Next Up (Phase 2)

- Add command router for post-handshake frames
- Implement placeholders for `LIST_CONVERSATIONS`, `START_SNAPSHOT`, and `CANCEL`
- Enforce active-operation constraints and `BUSY` handling
- Add smoke tests for protocol paths
