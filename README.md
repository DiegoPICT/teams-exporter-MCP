# Teams Chat Gateway Bridge

Experimental local bridge for a Teams chat exporter workflow.

This repository contains a small FastAPI-based bridge that maintains one local WebSocket session with an extension-side client and exposes a northbound HTTP API for local tools and automation.

This repository does not include the extension implementation itself.

## Status

- The bridge runtime remains the protocol/state substrate for the companion extension.
- Current active development focus is the MCP wrapper layer described in `docs/mcp-wrapper-implementation-plan.md`.
- Runtime limitations and hardening gaps are tracked in `KNOWN_ISSUES.md` and `TODO.md`.

## Companion Project Dependency

This bridge is designed to operate as the companion service for the extension work in:

- `https://github.com/DiegoPICT/teams-web-chat-exporter/tree/mcp-extension-targeted-snapshot-api-call`
- `https://github.com/DiegoPICT/teams-web-chat-exporter/blob/mcp-extension-targeted-snapshot-api-call/docs/EXTENSION_FOR_MCP.md`

The extension and bridge form one operational pair. The extension owns in-browser Teams runtime behavior, while this repository owns local orchestration and northbound API access.

Canonical dependency and compatibility guidance is maintained in `docs/companion-project.md`.

## Security and Privacy

- Treat this bridge as local-only software.
- The current HTTP and WebSocket surfaces are unauthenticated.
- Keep the bridge bound to `127.0.0.1` unless you are intentionally adding a security layer in front of it.
- Runtime logs, status data, and exported chat snapshots may contain sensitive metadata or content.
- See `SECURITY.md` and `KNOWN_ISSUES.md` before publishing logs, screenshots, or exported data.

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env` if you want to override defaults.
4. Run the bridge.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m bridge
```

Default endpoints:

- WebSocket: `ws://127.0.0.1:8765/ws`
- HTTP: `http://127.0.0.1:8765`

## Current API Surface

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

## Documentation

- `docs/README.md`: documentation index and reading order
- `docs/companion-project.md`: canonical bridge-to-extension dependency contract
- `docs/architecture.md`: high-level system boundaries and data flow
- `docs/northbound-api.md`: local HTTP API summary
- `docs/southbound-protocol.md`: WebSocket protocol summary and state model
- `docs/mcp-wrapper-implementation-plan.md`: canonical implementation plan for the MCP-facing wrapper
- `docs/development-testing.md`: local development and manual testing notes
- `KNOWN_ISSUES.md`: current limitations and public caveats
- `TODO.md`: parked improvements and future hardening work
- `SECURITY.md`: security posture, reporting guidance, and data-handling notes

Historical implementation notes remain under `docs/archive/` as non-canonical reference material.

## Repository Layout

- `bridge.py`: FastAPI application entrypoint and WebSocket route
- `service.py`: bridge state machine and operation coordination
- `northbound.py`: HTTP routes and SSE streaming
- `southbound.py`: WebSocket session adapter
- `frame_helper.py`: canonical frame helpers
- `logging_helper.py`: canonical logging setup
- `testing/emulate_consumer.py`: manual local consumer harness
- `testing/output/`: ignored local exports created by the test harness

## Public Repo Notes

- Local artifact hygiene is enforced through `.gitignore`.
- The consumer test harness now writes exports to `testing/output/` instead of the repo root.
- Historical path checks on reachable git history did not show committed `.env`, log files, chat export JSON, `__pycache__`, or `.venv` contents.

## Contributing

See `CONTRIBUTING.md` before opening a pull request. Keep architecture boundaries intact: bridge core remains the transport/state substrate, and MCP-facing behavior should be implemented in the wrapper layer.

## Disclaimer

This project is provided to work within the user's existing environment and operational context. You are solely responsible for using, configuring, and operating it in a way that complies with all applicable vendor terms, internal company policies, security requirements, and Microsoft terms of service.

This project is an independent effort and is not affiliated with, sponsored by, endorsed by, or approved by Microsoft.
