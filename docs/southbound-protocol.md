# Southbound Protocol

## Purpose

The southbound interface is the WebSocket connection between the local bridge and an extension-side client.

Canonical dependency context for the companion extension is documented in `docs/companion-project.md`.

## Transport

- default endpoint: `ws://127.0.0.1:8765/ws`
- protocol identifier: `teams-exporter-bridge/v1`
- one connected extension session at a time

## Handshake

1. The client connects to `/ws`.
2. The client sends `HELLO`.
3. The bridge validates the protocol version and responds with `HELLO_ACK`.
4. Session metadata from `HELLO.payload` becomes the active bound context.

## Keepalive and Connection Liveness

To prevent Chromium from terminating the Manifest V3 background service worker due to inactivity, the connection implements a **bi-directional keepalive** heartbeat:
- **Client to Bridge:** The extension sends a `PING` frame every 15 seconds. The bridge responds with a `PONG` frame.
- **Bridge to Client:** If the bridge detects no incoming frames for 15 seconds, it proactively sends a `PING` frame to the extension. The extension replies with a `PONG` frame.

This continuous exchange of native network events reliably resets the browser's 30-second idle timer, preserving the connection.

## Frame Envelope

Frames are JSON objects with a common envelope:

```json
{
  "v": "teams-exporter-bridge/v1",
  "type": "FRAME_TYPE",
  "requestId": "optional-request-id",
  "ts": 1760000000000,
  "payload": {},
  "error": "optional-error-text"
}
```

## Directionality

Bridge to extension commands:

- `LIST_CONVERSATIONS`
- `START_SNAPSHOT`
- `CANCEL`
- `GET_LOGS`
- `HEALTH`
- `API_CALL`
- `PING`
- `PONG`

Extension to bridge responses and events:

- `CONVERSATIONS`
- `SNAPSHOT_STARTED`
- `CHUNK`
- `DONE`
- `LOGS_RESULT`
- `HEALTH_RESULT`
- `API_RESULT`
- `ERROR`
- `PING`
- `PONG`

These frame expectations are defined by the bridge-companion pairing and are not claimed to be cross-fork universal.

## State and Operation Rules

- one active operation at a time
- request correlation uses `requestId`
- `BUSY` indicates concurrent work is not allowed
- `CANCEL` is intended to be idempotent
- disconnect and context loss are terminal for in-flight operations

## Streaming Semantics

Snapshot success flow:

1. `SNAPSHOT_STARTED`
2. zero or more `CHUNK`
3. terminal `DONE`

Chunk sizing is extension-owned behavior and not part of the stable contract.

## Security Note

The southbound WebSocket does not currently enforce origin or application-level authentication. Treat it as a local-only interface.
