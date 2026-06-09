# Documentation Index

This repository uses a canonical docs set centered on the companion relationship with the extension project.

## Read First

1. `docs/companion-project.md`
2. `docs/architecture.md`
3. `docs/northbound-api.md`
4. `docs/southbound-protocol.md`
5. `docs/development-testing.md`

## Scope

- `docs/companion-project.md`: authoritative dependency contract for the companion extension fork/branch
- `docs/architecture.md`: bridge responsibilities and system boundaries
- `docs/northbound-api.md`: local HTTP consumer surface
- `docs/southbound-protocol.md`: bridge WebSocket frame contract against the companion extension
- `docs/development-testing.md`: local setup and manual validation flow

## Historical Notes

- `docs/archive/` is retained for historical context only.
- Archived files are non-canonical and may contain stale implementation notes.
- For current behavior and dependency expectations, use the canonical docs listed above.

## Project-Level References

- `KNOWN_ISSUES.md`: user-visible limitations and coupling caveats
- `TODO.md`: parked improvements and future hardening work
- `SECURITY.md`: security posture, reporting guidance, and sensitive-data handling
- `CONTRIBUTING.md`: contribution expectations during code freeze
