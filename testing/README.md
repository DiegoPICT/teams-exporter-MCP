# Testing Scripts

This directory provides standalone scripts to exercise the local bridge during development.

Interface references:

- Southbound contract: `../SOUTHBOUND.md`
- Northbound contract: `../NORTHBOUND.md`

## Scripts

- `emulate_consumer.py`: northbound consumer emulator over HTTP verbs.
- `emulate_extension.py`: southbound extension peer emulator over WebSocket.
- `smoke_phase3.py`: end-to-end smoke checks for separated northbound/southbound flow.
- `smoke_phase2.py`: compatibility wrapper that runs phase-3 smoke checks.

## Common Setup

Run from repo root with an active virtual environment:

```bash
source .venv/bin/activate
python -m bridge
```

Keep the bridge running in one terminal. Run emulators from another terminal.

## Consumer Emulator

Exercises northbound bridge behavior over HTTP (`/conversations`, `/snapshots`, `/snapshots/{requestId}/cancel`).

```bash
python testing/emulate_consumer.py --mode all
```

Useful modes:

- `--mode list`
- `--mode snapshot`
- `--mode cancel`
- `--mode all`

## Extension Emulator

Simulates extension-side responses while the bridge sends southbound commands.

```bash
python testing/emulate_extension.py --idle-timeout 40 --chunk-delay 1 --chunk-count 3
```

## Phase 3 Smoke Test

Runs a one-shot check for:

- extension handshake and session binding
- real northbound `GET /conversations` pass-through
- snapshot stream events (`SNAPSHOT_STARTED` + `CHUNK`)
- northbound busy response while snapshot is active
- cancellation path to terminal `DONE(cancelled)`

```bash
python testing/smoke_phase3.py
```

## Important Notes

- The bridge enforces one active session at a time.
- If one emulator is connected, the second connection will be rejected with close code `1013`.
- Use `log/bridge.log` to inspect bridge-side behavior during runs.
- `smoke_phase2.py` is retained only for backward-compatible command usage.
