# Northbound Interface (App Verbs)

This document defines the consumer-facing interface of the bridge.

Scope: app/automation/MCP-facing verbs that request bridge operations.

## Purpose

- Provide a stable consumer interface that does not expose raw extension frame contracts.
- Translate app verbs into southbound protocol commands through the shared bridge service.
- Surface deterministic operation status, streaming progress, and terminal outcomes.

## Boundary Rule

- Northbound handles app verbs.
- Southbound handles extension protocol frames.
- The two interfaces must remain separate modules and should only meet at the core service layer.

## Planned Interface Shape

Current observability endpoints:

- `GET /health`
- `GET /bridge/status`

Planned command endpoints:

- `GET /conversations`
- `POST /snapshots`
- `POST /snapshots/{requestId}/cancel`
- `GET /snapshots/{requestId}/events` (stream)

## Verb-to-Protocol Mapping

- `list_conversations` / `GET /conversations`
  - sends southbound `LIST_CONVERSATIONS`
  - returns pass-through `CONVERSATIONS.payload`
- `start_snapshot` / `POST /snapshots`
  - sends southbound `START_SNAPSHOT`
  - streams `SNAPSHOT_STARTED` + `CHUNK` until terminal `DONE`/`ERROR`
- `cancel` / `POST /snapshots/{requestId}/cancel`
  - sends southbound `CANCEL`
  - resolves on terminal cancellation completion

## Error Surface

Northbound should expose normalized errors while preserving original codes:

- `BUSY`: conflict/retryable
- `CONTEXT_LOST`: user action required
- disconnect/transport unavailable: reconnect required
- `UNSUPPORTED`: request validation/protocol mismatch path

## State Model Exposure

Northbound status should include at least:

- connection state (`CONNECTED_IDLE`, `BUSY`, `DISCONNECTED`, `ERROR`, terminal context-lost when implemented)
- active operation metadata (`type`, `requestId`)
- bound session metadata (`sessionId`, `tabId`, `conversationId`, `conversationTitle`)
- last error summary

## Testing Expectations

- Consumer-side tests should target northbound endpoints/verbs, not `/ws`.
- End-to-end tests should pair a northbound client with `testing/emulate_extension.py`.
