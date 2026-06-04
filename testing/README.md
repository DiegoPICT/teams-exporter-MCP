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

Exercises northbound bridge behavior over HTTP (`/conversations`, `/snapshots`, `/snapshots/{requestId}/cancel`).

```bash
python testing/emulate_consumer.py --mode all
```

Useful modes:

- `--mode list`
- `--mode snapshot`
- `--mode full-sync`
- `--mode export`
- `--mode cancel`
- `--mode all`

## Important Notes

- The bridge enforces one active session at a time.
- Use `log/bridge.log` to inspect bridge-side behavior during runs.
- For Phase 3+, consumer/app verbs use northbound HTTP endpoints instead of `/ws`.
