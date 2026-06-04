# Teams Chat Exporter MCP Bridge Implementation Plan

This document defines a phased implementation plan for the local WebSocket bridge and MCP-facing adapter described in `WEBSOCKET_BRIDGE_MCP_DESIGN.md`.

Interface boundary references:

- Southbound extension transport: `SOUTHBOUND.md`
- Northbound app/API verbs: `NORTHBOUND.md`

Goal: move from "extension shows disconnected" to a stable, testable bridge that supports the v1 protocol and MCP tool mapping.

## Current Status

Phase 1 is implemented and manually validated.
Phase 2 is complete with the protocol router and placeholder command flows.
Phase 3 is implemented with northbound-driven real pass-through streaming.

Implemented artifacts:

- `bridge.py`: FastAPI-based local WebSocket bridge entrypoint.
- `frame_helper.py`: canonical frame/envelope helper for consistent protocol responses.
- `requirements.txt`: runtime dependencies (`fastapi`, `uvicorn[standard]`, `python-dotenv`).
- `.env`: local defaults (`BRIDGE_HOST`, `BRIDGE_PORT`, `BRIDGE_PATH`).
- `.gitignore`: excludes `.venv`, caches, and local `.env`.
- `logging_helper.py` and `log/`: canonical structured logging to console and rotating file (`log/bridge.log`).
- `testing/emulate_consumer.py`: northbound consumer emulator over HTTP verbs.

Verified runtime behavior:

- Bridge starts on `127.0.0.1:8765` with WebSocket path `/ws`.
- Extension connects from popup and sends `HELLO`.
- Bridge responds with `HELLO_ACK` and keeps connection open.
- Disconnects and reconnects are handled cleanly (`code=1001` observed during manual testing).
- Dev hot-reload is enabled for local iteration (`python -m bridge` uses Uvicorn reload mode).
- Source edits trigger graceful reload cycles with stop/start lifecycle events in `log/bridge.log`.
- Northbound verbs (`/conversations`, `/snapshots`, `/snapshots/{requestId}/cancel`) trigger southbound protocol commands.
- Snapshot event streaming is available via `/snapshots/{requestId}/events` (SSE).

Notes:

- Initial manual run showed FastAPI `on_event` deprecation warnings.
- The bridge was migrated to lifespan handlers, so startup/shutdown now uses the current FastAPI pattern.

## Guiding Principles

- Build thin vertical slices that can be validated in the extension UI immediately.
- Keep protocol handling explicit and deterministic (`requestId` correlation, single active operation).
- Treat `CONTEXT_LOST` and socket disconnects as terminal session states.
- Preserve extension-owned payload shapes as pass-through data unless mapping is explicitly required.

## Phase 1: Connectivity Milestone (Completed)

Objective: make the extension successfully connect and remain connected to a local bridge.

Status: completed and validated.

Implemented scope:

- Start a local WebSocket server bound to `127.0.0.1:8765`.
- Expose a `/ws` route for bridge traffic.
- Accept connection from the extension.
- Receive and parse the extension `HELLO` frame.
- Respond with `HELLO_ACK` using protocol id `teams-exporter-bridge/v1`.
- Keep connection open and log inbound/outbound frame metadata.
- Add graceful shutdown handling.
- Reject non-`/ws` WebSocket paths.
- Enforce single active extension session.
- Return explicit `ERROR` (`UNSUPPORTED`) for post-handshake commands in Phase 1.

Out of scope for Phase 1:

- Full command handling for `LIST_CONVERSATIONS`, `START_SNAPSHOT`, `CANCEL`.
- MCP tool server integration.
- Persistent state, retries, reconnection policy, or production hardening.

Delivered:

- Runnable bridge process (single binary/script entrypoint).
- Configurable host/port/path defaults (`127.0.0.1:8765/ws`).
- Basic frame validator for required top-level fields (`v`, `type`, optional `payload`, etc.).
- Structured logs for connect, disconnect, hello received, hello-ack sent, and close reason.
- Local environment config support via `.env`.
- Auto-reload development run mode.

Milestone acceptance criteria:

- Extension "Connect MCP" succeeds.
- UI state changes from `disconnected` to connected.
- No immediate socket close (`1006`) after connect.
- Bridge logs one successful `HELLO` -> `HELLO_ACK` exchange per session.

Acceptance result: passed in manual tests (including reconnect cycle).

Validation performed:

1. Start bridge locally.
2. Open Teams tab and extension popup.
3. Click `Connect MCP`.
4. Confirm UI no longer shows "Unable to connect to MCP bridge".
5. Confirm bridge logs handshake and open connection.
6. Close popup/tab and verify bridge logs clean disconnect.
7. Reconnect and verify second successful `HELLO` -> `HELLO_ACK` exchange.

Current run command:

```bash
python -m bridge
```

## Phase 2: Protocol Skeleton (Command/Response Wiring)

Objective: implement command router and deterministic frame lifecycle without full data pipeline.

Scope:

- Parse bridge-side requests by `type`.
- Enforce one active operation at a time.
- Return `ERROR` with `payload.code: BUSY` on illegal concurrent operation attempts.
- Implement skeletal handlers:
  - `LIST_CONVERSATIONS` -> return empty/placeholder `CONVERSATIONS` response shape.
  - `START_SNAPSHOT` -> emit `SNAPSHOT_STARTED` then `DONE` with zero count.
  - `CANCEL` -> idempotent cancelled `DONE` behavior.
- Ensure all operation responses include correlated `requestId`.

Deliverables:

- Message router and per-command handlers.
- In-memory session state machine (`CONNECTED_IDLE`, `BUSY`, `CONTEXT_LOST`, `DISCONNECTED`, `ERROR`).
- Unified error path for malformed frame, unsupported command, and busy state.

Milestone acceptance criteria:

- Command frames are parsed and routed predictably.
- Concurrency rule is enforced.
- `requestId` correlation is visible in logs and responses.
- `CANCEL` is idempotent and produces terminal `DONE(cancelled)` semantics.

Status: completed and verified with local emulators and `testing/smoke_phase2.py`.

## Immediate Next Steps

1. Formalize and version northbound response schemas for MCP consumption.
2. Add richer stream diagnostics and per-operation metrics.
3. Add integration tests around disconnect and `CONTEXT_LOST` terminal semantics.
4. Implement MCP adapter on top of the extracted bridge service layer.
5. Add CI execution for smoke checks and lint/test gates.

Completed in this iteration:

- Added `frame_helper.py` as the canonical envelope builder (`make_frame`, `make_error`).
- Refactored `bridge.py` to use frame helper for `HELLO_ACK` and `ERROR` responses.
- Implemented post-handshake router for `LIST_CONVERSATIONS`, `START_SNAPSHOT`, and `CANCEL`.
- Implemented operation semantics including `BUSY`, idempotent cancel, and request correlation.
- Added explicit southbound/northbound interface docs (`SOUTHBOUND.md`, `NORTHBOUND.md`).
- Extracted southbound adapter (`southbound.py`), core service (`service.py`), and northbound routes (`northbound.py`).
- Implemented northbound command endpoints and SSE snapshot events.
- Converted consumer emulator to HTTP.

## Phase 3: Real Snapshot Streaming

Objective: connect protocol handlers to real extension-exported data flow.

Scope:

- Implement real `LIST_CONVERSATIONS` pass-through.
- Implement `START_SNAPSHOT` streaming:
  - emit `SNAPSHOT_STARTED` metadata
  - emit `CHUNK` frames with `index`, `totalChunks`, `messages`
  - emit terminal `DONE`
- Preserve extension chunk size behavior (do not hardcode as protocol guarantee).
- Handle cancellation while streaming.

Deliverables:

- End-to-end message stream from extension context into bridge frames.
- Stream-safe backpressure and send error handling.
- Reliable terminal event emission (`DONE` or `ERROR`).

Milestone acceptance criteria:

- Snapshot of real conversation data can be started and completed.
- Multiple `CHUNK` frames arrive in order and correlate to one request.
- Cancel mid-stream stops further chunks and emits cancelled `DONE`.

Status: completed with separated northbound/southbound flow.

## Phase 4: MCP Adapter Integration

Objective: expose bridge capabilities as MCP tools with stable error mapping.

Scope:

- Implement tool mapping:
  - `list_conversations`
  - `start_snapshot` (stream tool output from `CHUNK.messages`)
  - `cancel`
- Map bridge errors to MCP-friendly categories:
  - `BUSY` -> retryable conflict
  - `CONTEXT_LOST` -> user action required
  - socket close -> unavailable/reconnect required
- Add operation timeout policy in adapter layer.

Deliverables:

- MCP server/module exposing tools.
- Adapter bridge client with request correlation and timeout handling.
- Tool-level integration tests.

Milestone acceptance criteria:

- MCP client can invoke all three tools successfully.
- Snapshot output arrives incrementally as stream chunks.
- Error mapping is deterministic and human-readable.

## Phase 5: Hardening and Release Readiness

Objective: make the bridge robust for day-to-day use.

Scope:

- Add configuration validation and startup diagnostics.
- Improve observability (log levels, request-scoped ids, optional metrics).
- Add resilience checks (invalid payloads, abrupt disconnects, stale session cleanup).
- Add compatibility test matrix (browser/runtime versions).
- Finalize docs and operator runbook.

Deliverables:

- Unit + integration + smoke tests in CI.
- Release checklist and versioning notes.
- Troubleshooting section for common failures (including close `1006`).

Milestone acceptance criteria:

- Bridge passes automated test suite and manual smoke scenarios.
- Known error cases produce actionable messages.
- Documentation is sufficient for another developer to run and debug locally.

## Initial Backlog (Implementation Order)

1. Create bridge project skeleton and entrypoint. (completed)
2. Add WebSocket server + `/ws` route binding. (completed)
3. Add connection/session lifecycle logs. (completed)
4. Implement `HELLO` parse + `HELLO_ACK` response. (completed)
5. Verify extension connection milestone. (completed)
6. Add command router and Phase 2 handlers. (completed)
7. Add status/health HTTP endpoints. (completed)
8. Add real streaming integration. (completed)
9. Add MCP tool adapter. (next)
10. Add tests and hardening.

## Definition of Done for v1

- Meets protocol expectations in `WEBSOCKET_BRIDGE_MCP_DESIGN.md`.
- Extension can connect, list, snapshot, and cancel through bridge.
- MCP tools operate end-to-end with clear errors and stable streaming.
- Test coverage includes handshake, correlation, busy-state, context-lost, cancel, and disconnect paths.
