# Architecture

## Purpose

The bridge separates two interfaces:

- a southbound WebSocket connection used by an extension-side client
- a northbound HTTP API used by local tools, scripts, or future adapters

The core bridge service sits between those interfaces and owns session state, operation state, correlation, and lifecycle handling.

See `docs/companion-project.md` for the canonical bridge-to-extension dependency anchor.

## High-Level Shape

```mermaid
flowchart LR
    EXT[Extension-side client] <-- WebSocket --> WS[Southbound adapter]
    WS <--> CORE[Bridge service]
    CORE <--> API[Northbound HTTP API]
    API <--> TOOL[Local tools and scripts]
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

The repository is being prepared for public consumption without changing runtime behavior. Design follow-ups and implementation gaps are tracked in `KNOWN_ISSUES.md` and `TODO.md`.

The bridge remains intentionally coupled to the companion extension branch documented in `docs/companion-project.md`.
