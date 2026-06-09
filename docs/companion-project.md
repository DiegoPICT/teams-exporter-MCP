# Companion Project Dependency

## Why This Exists

This bridge is not a standalone product surface. It is the companion service for the extension implementation maintained in:

- `https://github.com/DiegoPICT/teams-web-chat-exporter/tree/mcp-extension-targeted-snapshot-api-call`

Extension MCP behavior and transaction semantics are documented in:

- `https://github.com/DiegoPICT/teams-web-chat-exporter/blob/mcp-extension-targeted-snapshot-api-call/docs/EXTENSION_FOR_MCP.md`

## Ownership Split

- Companion extension fork: browser-side runtime, Teams auth context, extraction behavior, and extension MCP client flows
- This bridge repository: local HTTP surface, frame correlation, bridge-side state machine, and local orchestration

## Expected Runtime Pairing

The bridge and companion extension are intended to run together as one operational pair.

- Bridge southbound frames assume the companion extension frame model and behavior contracts
- Bridge northbound semantics are a wrapper over extension-backed operations
- Manual testing in this repository presumes that companion extension implementation is connected

## Compatibility Policy

Compatibility is guaranteed only for the companion extension branch listed above.

Using this bridge with a different extension fork, branch, or protocol variant may break behavior such as:

- operation flow and `requestId` correlation
- snapshot lifecycle (`SNAPSHOT_STARTED`, `CHUNK`, `DONE`)
- diagnostics and API transaction behavior (`GET_LOGS`, `HEALTH`, `API_CALL`)
- error-code expectations (`BUSY`, `CONTEXT_LOST`, `UNSUPPORTED`, and related extension-side codes)

## Drift and Change Management

If companion extension behavior changes, bridge updates may be required.

When reporting issues, include:

- bridge commit SHA
- companion extension commit SHA or branch ref
- relevant endpoint and frame samples (sanitized)

## Scope Note

This repository does not bundle, vend, or publish the companion extension code itself. It documents and depends on it.
