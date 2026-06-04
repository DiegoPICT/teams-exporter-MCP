# Bridge/MCP Integration Design (v1)

Audience: developers implementing the local bridge and MCP-facing service that connect to this extension over WebSocket.

This document is implementation-oriented and describes exactly how the bridge should interact with the extension in v1.

For extension-side constraints and scope guardrails, see `EXTENSION_WEBSOCKET_CONNECT.md`.

## 1) Transport and Session Model

- Endpoint (default): `ws://127.0.0.1:8765/ws`
- Protocol id: `teams-exporter-bridge/v1`
- One extension session at a time.
- One active operation at a time (`LIST_CONVERSATIONS` or `START_SNAPSHOT`).
- No queueing in extension v1. Concurrent requests return `ERROR` with code `BUSY`.
- No extension auto-reconnect logic in v1; reconnect is explicit user action.

## 2) Frame Envelope

All frames are JSON objects with this envelope:

```json
{
  "v": "teams-exporter-bridge/v1",
  "type": "FRAME_TYPE",
  "sessionId": "uuid-like-string",
  "requestId": "client-request-id",
  "ts": 1760000000000,
  "payload": {},
  "error": "error text"
}
```

Notes:

- `payload` is optional.
- `error` is present only for failure frames.
- `requestId` should be provided by the bridge for operation correlation.

## 3) Handshake

On connect, extension sends `HELLO`:

```json
{
  "v": "teams-exporter-bridge/v1",
  "type": "HELLO",
  "sessionId": "...",
  "ts": 1760000000000,
  "payload": {
    "protocol": "teams-exporter-bridge/v1",
    "tabId": 123,
    "conversationId": "19:abc...@thread.v2",
    "conversationTitle": "Optional title"
  }
}
```

Bridge should respond:

```json
{ "v": "teams-exporter-bridge/v1", "type": "HELLO_ACK", "ts": 1760000000100 }
```

`HELLO_ACK` is informational in v1; extension does not block operations on it.

## 4) Bridge -> Extension Commands

### `LIST_CONVERSATIONS`

Request:

```json
{
  "v": "teams-exporter-bridge/v1",
  "type": "LIST_CONVERSATIONS",
  "requestId": "req-list-1",
  "ts": 1760000001000
}
```

Success response:

- `type: "CONVERSATIONS"`
- `payload.conversations`: array from extension picker pipeline
- `payload.folders`: optional folder list

Failure response:

- `type: "ERROR"`
- optional `payload.code` (`BUSY`, `CONTEXT_LOST`, etc.)

### `START_SNAPSHOT`

Request:

```json
{
  "v": "teams-exporter-bridge/v1",
  "type": "START_SNAPSHOT",
  "requestId": "req-snap-1",
  "ts": 1760000002000,
  "payload": {
    "startAt": "2026-06-01T00:00:00.000Z",
    "endAt": "2026-06-04T00:00:00.000Z",
    "includeReplies": true,
    "includeReactions": true,
    "includeSystem": false
  }
}
```

All payload fields are optional. Missing fields use extension defaults.

Success stream:

1. `SNAPSHOT_STARTED`
2. `CHUNK` (zero or more)
3. `DONE`

### `CANCEL`

Request:

```json
{
  "v": "teams-exporter-bridge/v1",
  "type": "CANCEL",
  "requestId": "req-snap-1",
  "ts": 1760000002500
}
```

Behavior:

- If snapshot is active, extension stops scrape and emits `DONE` with cancelled reason.
- If no snapshot is active, extension still emits `DONE` cancelled (idempotent cancellation behavior).

## 5) Extension -> Bridge Responses

### `CONVERSATIONS`

```json
{
  "type": "CONVERSATIONS",
  "requestId": "req-list-1",
  "payload": {
    "conversations": [ ... ],
    "folders": [ ... ]
  }
}
```

Treat conversation/folder row shapes as extension-owned data contracts (pass-through), not bridge-owned schema.

### `SNAPSHOT_STARTED`

```json
{
  "type": "SNAPSHOT_STARTED",
  "requestId": "req-snap-1",
  "payload": {
    "count": 1432,
    "chunks": 8,
    "conversationId": "19:abc...",
    "conversationTitle": "Optional"
  }
}
```

### `CHUNK`

```json
{
  "type": "CHUNK",
  "requestId": "req-snap-1",
  "payload": {
    "index": 0,
    "totalChunks": 8,
    "messages": [ ...ExportMessage rows... ]
  }
}
```

Implementation note:

- v1 chunking is transport paging over an in-memory snapshot.
- Current chunk size is extension-internal (presently 200 messages) and not a protocol guarantee.

### `DONE`

Normal completion:

```json
{ "type": "DONE", "requestId": "req-snap-1", "payload": { "count": 1432 } }
```

Cancelled completion:

```json
{ "type": "DONE", "requestId": "req-snap-1", "payload": { "cancelled": true, "reason": "cancelled" } }
```

### `ERROR`

```json
{
  "type": "ERROR",
  "requestId": "req-snap-1",
  "payload": { "code": "BUSY" },
  "error": "Another operation is already running"
}
```

Known code values in v1:

- `BUSY`
- `CONTEXT_LOST`
- `UNSUPPORTED`

## 6) State Semantics Relevant to Bridge

- `CONNECTED_IDLE`: bridge may send a new operation.
- `BUSY`: one operation in flight; additional operations should not be sent.
- `CONTEXT_LOST`: bound Teams tab/conversation is no longer valid; bridge must stop requesting operations and require user reconnect in popup.
- `DISCONNECTED`: socket not available.
- `ERROR`: transport or operation-level failure; inspect `ERROR` frame details and/or close reason.

## 7) Scope Binding Rules

Session is bound to:

- one `tabId`
- one `conversationId`

The extension validates scope lazily before operations. If invalid, it emits `ERROR` with `code: CONTEXT_LOST` and moves to context-lost state.

Bridge must treat this as terminal for the session workflow (wait for explicit reconnect by user).

## 8) Reliability and Error Handling Guidance

Bridge should implement:

- Request correlation using `requestId`.
- Operation timeout policy on bridge side (extension v1 does not add layered custom timeouts).
- Idempotent cancel handling.
- Clean handling of socket close as terminal (`DISCONNECTED` path).

Bridge should not assume:

- Pull-based paging (`NEXT`) support.
- Multi-operation concurrency.
- Extension-side auto-reconnect.
- Application-level ping/pong.

## 9) MCP Adapter Mapping (Recommended)

Suggested MCP tool mapping:

- `list_conversations` -> send `LIST_CONVERSATIONS`, return `CONVERSATIONS` rows.
- `start_snapshot` -> send `START_SNAPSHOT`, stream `CHUNK.messages` as tool output chunks, close on `DONE`.
- `cancel` -> send `CANCEL`, expect `DONE(cancelled)`.

Error mapping recommendation:

- `BUSY` -> retryable conflict / "operation already running"
- `CONTEXT_LOST` -> user action required (re-open popup, reconnect MCP)
- socket close -> unavailable / reconnect required

## 10) Conformance Checklist for Bridge Developer

- Connect to loopback WS endpoint.
- Wait for `HELLO`, respond `HELLO_ACK`.
- Send only one active operation at a time.
- Always include `requestId`.
- Handle `ERROR` frames with `payload.code`.
- Handle `DONE(cancelled)` as successful cancellation, not failure.
- Treat `CONTEXT_LOST` as terminal until user reconnect.
- Do not depend on extension auto-reconnect or pull-iterator semantics.
