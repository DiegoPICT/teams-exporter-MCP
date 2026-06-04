# Testing Scripts

This directory provides standalone scripts to exercise the local bridge during development.

Interface references:

- Southbound contract: `../SOUTHBOUND.md`
- Northbound contract: `../NORTHBOUND.md`

## Scripts

- `emulate_consumer.py`: legacy phase-2 script that sends verbs over websocket (transitional).
- `emulate_extension.py`: acts like an extension peer and responds to bridge commands.
- `smoke_phase2.py`: automated smoke checks for Phase 2 command semantics.

## Common Setup

Run from repo root with an active virtual environment:

```bash
source .venv/bin/activate
python -m bridge
```

Keep the bridge running in one terminal. Run emulators from another terminal.

## Consumer Emulator

Exercises local Phase 2 placeholder behavior over WebSocket (`LIST_CONVERSATIONS`, `START_SNAPSHOT`, `CANCEL`).

Important: this script reflects the phase-2 transitional approach and is not the long-term northbound contract.

```bash
python testing/emulate_consumer.py --mode all
```

Useful modes:

- `--mode list`
- `--mode snapshot`
- `--mode cancel`
- `--mode all`

## Extension Emulator

Simulates extension-side responses when the bridge acts as command sender.

```bash
python testing/emulate_extension.py --idle-timeout 20
```

## Phase 2 Smoke Test

Runs a one-shot check for:

- handshake (`HELLO` -> `HELLO_ACK`)
- `LIST_CONVERSATIONS` placeholder
- `START_SNAPSHOT` placeholder start event
- `BUSY` behavior while snapshot is active
- `CANCEL` completion
- idempotent `CANCEL` when no snapshot is active

```bash
python testing/smoke_phase2.py
```

## Important Notes

- The bridge enforces one active session at a time.
- If one emulator is connected, the second connection will be rejected with close code `1013`.
- Use `log/bridge.log` to inspect bridge-side behavior during runs.
- For Phase 3+, consumer/app verbs should move to northbound endpoints instead of using `/ws`.
