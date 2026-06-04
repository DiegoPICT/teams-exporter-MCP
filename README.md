# teams-chat-gw-bridge-mcp

Local bridge service for Teams Chat Exporter, with a strict separation between:

- southbound extension WebSocket transport
- northbound app/API verb interface

This repository currently has Phase 1 and Phase 2 completed, and is preparing Phase 3 real streaming integration.

## Current Status

- Phase 1 complete: extension can connect to a local bridge and complete `HELLO` -> `HELLO_ACK`.
- Phase 2 complete: command/state skeleton and baseline observability are implemented.
- Phase 3 complete (with known bugs): northbound verbs drive real southbound streaming, but there are context-sync and export naming bugs to resolve.
- Auto-reload enabled for local development (`python -m bridge`).
- Canonical logging is enabled to console and `log/bridge.log`.
- Canonical frame helper is in place for consistent protocol envelopes.

## Documentation Map

- `README.md`: project quickstart and document index
- `DESIGN.md`: architecture overview (high level)
- `SOUTHBOUND.md`: extension-facing WebSocket interface boundary
- `NORTHBOUND.md`: app/API-facing verb interface boundary
- `WEBSOCKET_BRIDGE_MCP_DESIGN.md`: protocol-level contract details
- `IMPLEMENTATION.md`: phased delivery status and backlog

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

- Consumer emulator: `testing/emulate_consumer.py`

Usage guide:

- `testing/README.md`

## Repository Layout

- `bridge.py`: current FastAPI runtime (phase-1/phase-2 implementation)
- `frame_helper.py`: canonical frame builder utilities
- `logging_helper.py`: logger setup (console + rotating file)
- `testing/`: local emulation scripts for consumer behavior
- `SOUTHBOUND.md`: southbound extension transport contract
- `NORTHBOUND.md`: northbound app verb contract
- `IMPLEMENTATION.md`: phased delivery plan and status
- `DESIGN.md`: target architecture and data flow
- `WEBSOCKET_BRIDGE_MCP_DESIGN.md`: protocol-level contract and semantics

## Next Up (Phase 4)

Gap analysis and planning for the MCP adapter wrapper.
