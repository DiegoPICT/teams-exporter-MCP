# Southbound Interface (Extension WebSocket)

This document defines the extension-facing interface for the bridge.

Scope: communication between the local bridge and the Teams extension over WebSocket.

Canonical protocol reference remains `WEBSOCKET_BRIDGE_MCP_DESIGN.md`. This doc focuses on interface boundaries and operational expectations.

## Purpose

- Maintain one active extension session over WebSocket.
- Exchange protocol frames with deterministic request correlation.
- Carry bridge-initiated commands and extension-originated responses/events.

## Transport

- Endpoint: `ws://127.0.0.1:8765/ws`
- Protocol id: `teams-exporter-bridge/v1`
- Session model: one extension session at a time

## Directionality

After handshake, the direction is fixed:

- Bridge -> Extension commands:
  - `LIST_CONVERSATIONS`
  - `START_SNAPSHOT`
  - `CANCEL`
  - `GET_LOGS`
  - `HEALTH`
  - `API_CALL`
- Extension -> Bridge responses/events:
  - `CONVERSATIONS`
  - `SNAPSHOT_STARTED`
  - `CHUNK`
  - `DONE`
  - `LOGS_RESULT`
  - `HEALTH_RESULT`
  - `API_RESULT`
  - `ERROR`

The extension WebSocket is not the consumer/app verb interface.

## Handshake

- Extension sends `HELLO` on connect.
- Bridge validates protocol/version and returns `HELLO_ACK`.
- Session metadata from `HELLO.payload` is recorded as bound scope context.

## Session and Operation Semantics

- One active operation at a time.
- `requestId` is required for operation correlation.
- `BUSY` must be returned for concurrent operation attempts.
- `CANCEL` is idempotent and resolves via terminal `DONE(cancelled)` behavior.
- `CONTEXT_LOST` is terminal until explicit reconnect.

## Streaming Semantics

`START_SNAPSHOT` success path:

1. `SNAPSHOT_STARTED`
2. zero or more `CHUNK`
3. terminal `DONE`

Notes:

- Chunk size is extension-internal and not a protocol guarantee.
- Late/out-of-order frames after terminal completion should be ignored and logged.

## Error and Disconnect Handling

- `ERROR.payload.code` values are protocol-significant (`BUSY`, `CONTEXT_LOST`, `UNSUPPORTED`).
- Socket close is terminal for in-flight operations.
- In-flight operation waiters/streams must resolve on disconnect.

## Ownership Boundary

Southbound adapter responsibilities:

- socket lifecycle
- frame I/O
- protocol validation
- forwarding frames to core bridge service

Southbound adapter should not own app-facing verb semantics beyond transport enforcement.

## Validation Harness

- Log file: `log/bridge.log`
