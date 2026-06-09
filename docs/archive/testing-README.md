# Testing Scripts

This directory provides standalone scripts to exercise the local bridge during development.

Interface references:

- Southbound contract: `../SOUTHBOUND.md`
- Northbound contract: `../NORTHBOUND.md`

## Scripts

- `emulate_consumer.py`: northbound consumer emulator over HTTP verbs.

## Common Setup

Run from repo root with an active virtual environment:

```bash
source .venv/bin/activate
python -m bridge
```

Make sure the real Teams Extension is connected to the bridge.

## Consumer Emulator

Exercises northbound bridge behavior over HTTP (`/conversations`, `/snapshots`, `/snapshots/{requestId}/cancel`, `/extensions/api-call`).

Useful modes:

- `--mode status`
- `--mode list-chats`
- `--mode active-chat`
- `--mode specific-chat --chat-index 3`
- `--mode extension-api --api-method GET --api-endpoint /api/chats`

Examples:

```bash
python testing/emulate_consumer.py --mode list-chats
python testing/emulate_consumer.py --mode active-chat
python testing/emulate_consumer.py --mode specific-chat --chat-index 1
python testing/emulate_consumer.py --mode extension-api --api-method GET --api-endpoint /api/chats
```

## Important Notes

- The bridge enforces one active session at a time.
- Use `log/bridge.log` to inspect bridge-side behavior during runs.
- For Phase 3+, consumer/app verbs use northbound HTTP endpoints instead of `/ws`.
