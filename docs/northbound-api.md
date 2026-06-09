# Northbound API

## Purpose

The northbound API is the local consumer-facing interface of the bridge. It translates local HTTP requests into bridge operations without exposing raw extension frame contracts directly.

Its behavior is companion-coupled to the extension branch documented in `docs/companion-project.md`.

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

## Error Surface

Current bridge errors preserve a code and HTTP status where possible. Common error codes include:

- `BUSY`
- `CONTEXT_LOST`
- `DISCONNECTED`
- `TIMEOUT`
- `UNSUPPORTED`

## Security Note

The northbound API is currently unauthenticated and should be treated as local-only.
