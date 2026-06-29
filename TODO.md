# TODO

This file tracks parked improvements that are intentionally not being implemented in the current implementation window.

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

- Implement MCP wrapper delivery phases defined in `docs/mcp-wrapper-implementation-plan.md`.
- Revisit protocol ergonomics and error semantics after automated coverage exists.
