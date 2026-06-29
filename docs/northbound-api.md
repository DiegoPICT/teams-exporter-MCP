# Northbound API

## Purpose

The northbound API is the local bridge interface used to trigger bridge operations and stream results without exposing raw extension frame contracts directly.

Its behavior is companion-coupled to the extension branch documented in `docs/companion-project.md`.

Current architectural intent is to keep this HTTP/SSE surface as the bridge substrate and expose a higher-level MCP consumer contract through a dedicated wrapper layer.

## Endpoints

Observability:

- `GET /health`
- `GET /bridge/status`

Operations:

- `GET /conversations`
- `POST /snapshots`
- `GET /snapshots/{requestId}/events`
- `POST /snapshots/{requestId}/cancel`
- `POST /extensions/logs`
- `POST /extensions/health`
- `POST /extensions/api-call`

## Current Semantics

- `GET /conversations` requests a conversation listing from the connected extension session.
- `POST /snapshots` starts a snapshot operation and returns a `requestId`.
- `GET /snapshots/{requestId}/events` streams operation events as server-sent events.
- `POST /snapshots/{requestId}/cancel` requests cancellation for the active snapshot.
- `POST /extensions/logs`, `POST /extensions/health`, and `POST /extensions/api-call` pass through extension-side diagnostics or API transactions.

For extension-side MCP transaction semantics, see the companion extension reference linked from `docs/companion-project.md`.

For MCP-wrapper implementation intent and phased delivery, see `docs/mcp-wrapper-implementation-plan.md`.

## Error Surface

Current bridge errors preserve a code and HTTP status where possible. Common error codes include:

- `BUSY`
- `CONTEXT_LOST`
- `DISCONNECTED`
- `TIMEOUT`
- `UNSUPPORTED`

## Security Note

The northbound API is currently unauthenticated and should be treated as local-only.
