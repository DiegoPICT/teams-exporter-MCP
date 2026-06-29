# Architecture

## Purpose

The bridge separates two primary interfaces:

- a southbound WebSocket connection used by an extension-side client
- a northbound HTTP API used as the local substrate for tools and adapters

The core bridge service sits between those interfaces and owns session state, operation state, correlation, and lifecycle handling.

The intended consumer-facing layer is an MCP wrapper that calls the northbound HTTP/SSE API rather than bridge internals.

See `docs/companion-project.md` for the canonical bridge-to-extension dependency anchor.

## High-Level Shape

```mermaid
flowchart LR
    EXT[Extension-side client] <-- WebSocket --> WS[Southbound adapter]
    WS <--> CORE[Bridge service]
    CORE <--> API[Northbound HTTP API]
    API <--> MCP[MCP wrapper]
    MCP <--> TOOL[LLM and local MCP clients]
```

## Current Boundaries

- `bridge.py`: application entrypoint and WebSocket route
- `southbound.py`: socket lifecycle and frame I/O
- `service.py`: connection state and operation coordination
- `northbound.py`: HTTP routes and SSE streaming
- `frame_helper.py`: frame construction helpers
- `logging_helper.py`: canonical logger setup

## Operational Constraints

- one extension session at a time
- one active operation at a time
- request correlation is done with `requestId`
- disconnect and context loss are terminal for in-flight work

## Current Intent

The bridge runtime remains intentionally stable as the protocol/state substrate for the companion extension.

Active design and implementation work is focused on the MCP wrapper layer, tracked in `docs/mcp-wrapper-implementation-plan.md`.

The bridge remains intentionally coupled to the companion extension branch documented in `docs/companion-project.md`.
