# TODO

This file tracks parked improvements that are intentionally not being implemented during the current cleanup phase.

## Security and Hardening

- Add authentication and authorization for northbound endpoints.
- Add origin and session validation for the southbound WebSocket.
- Narrow the exposure of session metadata in status and logs.
- Add explicit retention limits for snapshot history and streamed events.

## API and Validation

- Replace raw `dict` request bodies with typed request models.
- Improve `API_CALL` validation and preserve richer upstream error information.
- Review handshake ordering so only validated extension clients become the active session.

## Testing and Automation

- Add automated tests for handshake validation, disconnect handling, SSE delivery, and timeout paths.
- Add a lightweight CI workflow for linting, smoke tests, and basic repository checks.
- Add release notes or changelog discipline once the repo moves beyond prototype status.

## Project Hygiene

- Decide whether the public default branch should remain `master` or be renamed to `main`.
- Keep bridge docs deduplicated around `docs/companion-project.md` as the single source of truth for extension dependency.
- Add a lightweight compatibility matrix mapping bridge commits to tested companion extension refs.

## Product and Protocol Work

- Add MCP adapter work when the code freeze is lifted.
- Revisit disconnect and reconnect behavior once feature work resumes:
  - **Client-Side Keepalive Heartbeat:** Implement a periodic 15-20 second `PING` frame sent by the companion extension over the WebSocket. The bridge should either handle this as a keepalive tick or ignore it gracefully to prevent MV3 background service worker termination.
  - **Persistent Connection Intent:** Save the active connection state (`mcpConnectionIntent`) in `chrome.storage.local` within the extension background script. On startup, read the storage and auto-reconnect if connection was active, preventing desynchronization on worker restart.
  - **Alarms-Based Self-Healing:** Establish a 1-minute chrome alarm to periodically wake up the worker, inspect the connection state, and automatically rebuild/re-authenticate the socket if it dropped unexpectedly.
- Revisit protocol ergonomics and error semantics after automated coverage exists.
