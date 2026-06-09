# Known Issues

This repository is intentionally documenting current limitations instead of addressing them during the current code-freeze phase.

## Security Model

- The northbound HTTP API is currently unauthenticated.
- The southbound WebSocket session does not currently enforce origin or application-level authentication.
- The bridge should be treated as local-only software and kept on loopback unless you add a security boundary in front of it.

## Sensitive Data Exposure

- `GET /bridge/status` exposes session metadata such as `sessionId`, `tabId`, `conversationId`, and `conversationTitle` when present.
- Runtime logs may contain metadata that is operationally useful but sensitive in public bug reports.
- Exported chat snapshots can contain message content, participant names, identifiers, and timestamps.

## Runtime Behavior

- Snapshot events are retained in memory without an eviction policy.
- `API_CALL` validation and error mapping are intentionally thin.
- The runtime defaults are still development-oriented, including hot reload in the local entrypoint.
- The bridge currently supports one connected extension session and one active operation at a time.

## Testing and Release Readiness

- The repository currently relies on manual validation rather than automated unit or integration tests.
- There is no CI workflow in this repository yet.
- There is no release automation or packaged distribution flow yet.

## Artifact Hygiene

- Runtime logs, local `.env` files, and test exports must not be committed.
- The consumer test harness now writes exports to `testing/output/`, which is ignored.
- As of the current cleanup pass, reachable git history checks did not show committed `.env`, exported chat JSON, log files, `__pycache__`, or `.venv` contents.
