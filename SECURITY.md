# Security Policy

## Supported Versions

- The current default branch is the only supported line.
- Historical snapshots and archived planning documents are provided for reference only.

## Current Security Posture

- This repository currently ships a local bridge prototype.
- The bridge is designed to run on loopback by default.
- The current HTTP and WebSocket interfaces are not authenticated.
- Do not expose the bridge directly to untrusted networks in its current form.

## Sensitive Data Handling

- Do not commit `.env` files, logs, exported chat snapshots, or browser-derived session data.
- Do not paste raw chat exports, bearer tokens, cookies, or screenshots containing personal data into public issues.
- The manual test harness writes exports to `testing/output/`, which is ignored by git.

## Repository Hygiene Notes

- The repository ignores local runtime artifacts such as `.env`, logs, virtual environments, caches, and test outputs.
- A reachable-history audit performed during the public cleanup pass did not show committed `.env`, exported chat JSON, log files, `__pycache__`, or `.venv` contents.
- If a sensitive artifact is discovered later in history, treat it as a security incident and rotate any affected credentials before considering history rewriting.

## Reporting a Vulnerability

- Prefer a private reporting path if one is available on GitHub.
- If private reporting is not enabled, contact the repository owner through GitHub before opening a public issue for an active vulnerability.
- Include reproduction steps, affected files or endpoints, and impact assessment.
- Sanitize all logs and payload examples before sharing them.

## Scope

- This repository only contains the local bridge and manual test harness.
- If an issue depends on private extension code or external services, report the bridge-side impact and any known dependencies clearly.
