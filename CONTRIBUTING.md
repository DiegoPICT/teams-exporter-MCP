# Contributing

## Current Contribution Scope

- The runtime is currently in code freeze.
- Repository hygiene, documentation cleanup, GitHub metadata, and security-oriented housekeeping are the preferred contribution areas.
- Larger runtime or protocol changes should be discussed before implementation.

## Before Opening a Pull Request

- Read `README.md`, `SECURITY.md`, `KNOWN_ISSUES.md`, and `TODO.md`.
- Keep changes small and easy to review.
- Avoid mixing repo-cleanup work with unrelated runtime changes.
- Do not commit `.env`, logs, exported chat snapshots, or local test artifacts.

## Development Notes

- Create a local virtual environment and install dependencies from `requirements.txt`.
- Use `.env.example` as the starting point for local configuration.
- Use `testing/emulate_consumer.py` for manual local validation when needed.
- Test exports belong in `testing/output/`, which is ignored.

## Security Expectations

- Do not open public issues for active credential leaks or sensitive-data exposure without sanitizing the report.
- Follow `SECURITY.md` for vulnerability reporting.

## Pull Request Guidance

- Explain what changed and why.
- Mention any documentation updates that were added or intentionally deferred.
- Call out any remaining risks or follow-up items.
