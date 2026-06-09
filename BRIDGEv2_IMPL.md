# Bridge v2 Implementation Plan (Remaining Features)

This document defines the bridge-side implementation plan for the remaining v2 scope, aligned with:

- `V2_FEATURE_INTENTS.md`
- extension-side plan (`EXTENSIONv2_IMPL.md`)

## Scope

In scope:

1. Deterministic message iteration semantics for `START_SNAPSHOT`:
   - active chat mode (GUI-selected chat)
   - specific chat mode (`conversationId` override)
2. Generic Teams API transaction:
   - `API_CALL` request
   - `API_RESULT` response

Already delivered (not part of this plan):

- `GET_LOGS` / `LOGS_RESULT`
- `HEALTH` / `HEALTH_RESULT`

Out of scope (parked):

- Extension/runtime reconnect policy tuning (`1001` reliability follow-up)
- Proactive context push frames
- Queueing / iterator redesign

## Guardrail Decision

For `API_CALL`, bridge starts as a **thin pass-through** with basic shape validation only.

- Bridge validates presence and type of essential fields.
- Extension remains authoritative for runtime/API guardrails and policy enforcement.
- Avoid duplicated policy logic between bridge and extension.

## Current Bridge Baseline

Implemented now:

- Southbound commands: `LIST_CONVERSATIONS`, `START_SNAPSHOT`, `CANCEL`, `GET_LOGS`, `HEALTH`
- Southbound responses: `CONVERSATIONS`, `SNAPSHOT_STARTED`, `CHUNK`, `DONE`, `LOGS_RESULT`, `HEALTH_RESULT`, `ERROR`
- Northbound endpoints:
  - `GET /conversations`
  - `POST /snapshots`
  - `POST /snapshots/{requestId}/cancel`
  - `GET /snapshots/{requestId}/events`
  - `POST /extensions/logs`
  - `POST /extensions/health`

## Feature 1 Plan: Deterministic Snapshot Targeting

### Objective

Ensure bridge semantics are deterministic and observable when iterating messages either for:

- active GUI-selected chat (`conversationId` omitted), or
- explicitly requested chat (`conversationId` provided).

### Bridge Responsibilities

1. Preserve request intent from northbound payload:
   - if `conversationId` present, forward it unchanged to extension
   - if omitted, forward active-mode request unchanged
2. Add observability for target determinism:
   - record expected target conversation for each snapshot operation
   - compare expected vs `SNAPSHOT_STARTED.payload.conversationId` when available
3. Emit explicit mismatch diagnostics if extension starts a different chat than requested.

### Minimal Data Model Update

In `SnapshotOperation`, add optional fields:

- `expected_conversation_id: str | None`
- `started_conversation_id: str | None`
- `started_conversation_title: str | None`

### Mismatch Handling Policy (Bridge)

If targeted mode requested and `SNAPSHOT_STARTED` reports a different conversation id:

- log a high-signal mismatch event with expected/actual ids
- publish terminal `ERROR` frame to event stream with deterministic code (e.g. `TARGET_MISMATCH`)
- clear operation

This avoids silent wrong-chat exports from bridge consumers.

## Feature 2 Plan: `API_CALL` / `API_RESULT`

### Objective

Expose a generic bridge transaction to ask extension for authenticated Teams API calls and return raw result data + status + error.

### Bridge Contract

- New command frame: `API_CALL`
- New response frame: `API_RESULT`

### Core Service Changes (`service.py`)

1. Add constants:
   - `API_CALL`
   - `API_RESULT`
2. Add operation holder:
   - `ApiOperation(request_id, result_future)`
3. Add active operation slot:
   - `active_api_operation`
4. Implement method:
   - `api_call(payload: dict[str, Any]) -> dict[str, Any]`
   - enforce existing BUSY semantics
   - send `API_CALL`
   - await correlated `API_RESULT` with timeout
5. Route `API_RESULT` in frame handler.
6. Route correlated `ERROR` to resolve the API operation failure path.

### Northbound API Changes (`northbound.py`)

Add endpoint:

- `POST /extensions/api-call`

Behavior:

- receives JSON payload
- forwards to `bridge_service.api_call(...)`
- returns pass-through `API_RESULT.payload`
- uses existing `BridgeServiceError` -> HTTP mapping

### Basic Bridge Input Validation (thin)

Before send, validate only:

- payload is object
- `method` is non-empty string
- `endpoint` is non-empty string

If invalid, return `400` with `UNSUPPORTED`/validation code.

No host/method policy duplication at bridge layer in this phase.

## File Touch Plan

Primary:

- `service.py`
  - operation model + frame routing + error routing for `API_CALL`/`API_RESULT`
  - snapshot target observability/mismatch handling
- `northbound.py`
  - add `POST /extensions/api-call`

Docs:

- `NORTHBOUND.md`
  - add endpoint and mapping
- `SOUTHBOUND.md`
  - add frame types and semantics
- `IMPLEMENTATION.md`
  - progress and remaining TODOs

Testing harness:

- `testing/emulate_consumer.py`
  - add `extension-api` mode
  - add targeted snapshot determinism checks

## Rollout Sequence

1. Implement `API_CALL` / `API_RESULT` in core + northbound.
2. Add snapshot target observability and deterministic mismatch handling.
3. Update docs and test harness.
4. Run validation matrix once before merge.

## Acceptance Criteria

### Feature 1 (snapshot targeting)

- Active mode works with omitted `conversationId`.
- Targeted mode sends requested `conversationId` unchanged.
- If extension starts different chat than requested, bridge emits deterministic terminal error and logs expected/actual values.

### Feature 2 (`API_CALL`)

- Valid requests return `API_RESULT` payload via `POST /extensions/api-call`.
- Invalid bridge payload returns deterministic 4xx validation error.
- Correlated extension `ERROR` frames propagate cleanly to northbound caller.

### System

- Existing `BUSY` model remains unchanged.
- Existing logs/health transactions remain unchanged.
- Existing snapshot and conversations behavior remains backward-compatible.

## Validation Matrix

1. `POST /extensions/health` confirms connected extension version/protocol.
2. `POST /extensions/api-call` with valid payload -> deterministic result.
3. `POST /extensions/api-call` malformed payload -> deterministic 400 error.
4. `POST /snapshots` active mode -> reports active chat in `SNAPSHOT_STARTED`.
5. `POST /snapshots` targeted mode valid id -> started id matches requested.
6. `POST /snapshots` targeted mode mismatch -> deterministic terminal `TARGET_MISMATCH`.
7. Concurrency test -> second operation returns `BUSY`.
