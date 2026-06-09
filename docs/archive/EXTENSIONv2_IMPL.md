# Extension v2 Implementation Plan (Two Remaining Features)

This plan implements only the remaining v2 feature intents in
`V2_FEATURE_INTENTS.md` with additive, minimal, upstream-respectful changes.

## Scope

In scope:

- Feature 1: deterministic chat targeting for `START_SNAPSHOT`
- Feature 2: generic Teams API transaction (`API_CALL` / `API_RESULT`)

Already delivered (not part of this plan):

- `GET_LOGS` / `LOGS_RESULT`
- `HEALTH` / `HEALTH_RESULT`

Out of scope (parked):

- Auto-reconnect and lifecycle tuning
- Proactive context push frames
- Queueing / iterator redesign

## Non-Negotiable Implementation Principles

- Additive protocol evolution only; no breaking v1 behavior.
- Minimal touch set; avoid broad refactors.
- Keep MCP single-operation `BUSY` model unchanged.
- Deterministic behavior over heuristics.
- No bridge-policy duplication in extension (bridge is primary guardrail).
- No popup UX churn unless strictly required (none expected here).

## Current Hooks We Reuse

- MCP frame dispatch and operation lifecycle in `src/entrypoints/background.ts`.
- Existing targeted scrape hook: `ScrapeOptions.conversationId`.
- Existing wrong-target safety: `ScrapeOptions.noDomFallback`.
- Existing content runtime bridge (`runtime.onMessage`) in
  `src/entrypoints/content.ts`.
- Existing API auth/discovery primitives in `src/content/api-client.ts`.

## Feature 1 Plan: Deterministic `START_SNAPSHOT`

### Intent Mapping

- Targeted mode: `payload.conversationId` provided -> stream exactly that chat.
- Active mode: `payload.conversationId` omitted -> stream current GUI chat.
- No silent fallback from targeted -> active.

### Implementation Steps

1. In `handleMcpStartSnapshot`, parse optional `payload.conversationId` and
   optional `payload.conversationTitle`.
2. Compute effective target:
   - targeted mode -> use requested id directly,
   - active mode -> resolve current GUI chat via existing `getConvIdForTab`.
3. Build `ScrapeOptions` with effective `conversationId`.
4. Set `noDomFallback: true` in targeted mode to prevent silent drift to active
   GUI chat when API path fails.
5. Emit `SNAPSHOT_STARTED` using effective id/title as source of truth.
6. Return deterministic terminal errors for invalid/unreachable targets.

### Error Semantics

- `BUSY`: concurrent operation attempted.
- `CONTEXT_LOST`: tab/scope no longer valid.
- `NOT_FOUND` (or equivalent mapped error): requested chat does not resolve.
- `UNSUPPORTED`: invalid frame/parameter shape.

### Minimal-Churn Notes

- No tab-switch automation.
- No DOM navigation logic.
- No new popup behavior required.

## Feature 2 Plan: Generic `API_CALL` / `API_RESULT`

### Intent Mapping

- Bridge sends generic API requests; extension executes authenticated in-page
  calls and returns raw result/status/error deterministically.

### Contract

- Request frame: `API_CALL`
  - `method` (not restricted to GET-only)
  - `endpoint`
  - optional `query`
  - optional `body`
- Response frame: `API_RESULT`
  - `status`
  - `data`
  - `error`

### Extension-Side Guardrails (Basic by Design)

- Payload shape validation.
- Method normalization and rejection of empty/invalid method.
- Request timeout cap.
- Response size cap (stability guard).
- Deterministic structured errors.

The extension does not attempt to replicate bridge policy decisions; it only
enforces runtime correctness and stability.

### Implementation Steps

1. Add `API_CALL` handling in background MCP frame router.
2. Reuse single-operation busy gate.
3. Forward validated API request to content script via runtime message
   (new narrow message type).
4. In content layer, add one small execution path that reuses existing
   auth/discovery primitives from `api-client.ts`.
5. Normalize content response to `API_RESULT` with stable shape.
6. Map malformed payload/runtime failures to deterministic `ERROR`/`API_RESULT.error`.

### Minimal-Churn Notes

- No new transport channel.
- No new persistence state.
- No popup changes.

## File Touch Plan (Minimal)

Primary:

- `src/entrypoints/background.ts`
  - `START_SNAPSHOT` deterministic mode logic
  - `API_CALL` frame handler and orchestration
- `src/entrypoints/content.ts`
  - one new runtime message branch for API execution
- `src/content/api-client.ts`
  - one small helper exported for generic API execution
- `src/types/messaging.ts`
  - additive typing for new runtime message and result shapes

Optional docs update after implementation:

- `WEBSOCKET.md` (brief index/reference refresh)

## Rollout Sequence (Avoid Band-Aiding)

1. Implement Feature 1 fully (targeted + active mode) and verify determinism.
2. Implement Feature 2 with basic extension rails and stable contract.
3. Run full validation once; avoid iterative hotfix churn by locking contract
   examples before merge.

## Acceptance Criteria

Feature 1:

- Targeted mode returns `SNAPSHOT_STARTED.conversationId == requested` or
  explicit terminal error.
- Active mode resolves and reports current GUI-selected chat.
- No targeted->active silent fallback.

Feature 2:

- Valid request returns deterministic `API_RESULT` (`status`, `data`, `error`).
- Invalid request returns deterministic error with reason.
- Non-GET methods are supported by contract (not artificially blocked).

System:

- Existing MCP connect/disconnect/status flows remain intact.
- Single-operation `BUSY` semantics remain unchanged.

## Verification Checklist

Bridge-side protocol checks:

1. `START_SNAPSHOT` targeted with valid id.
2. `START_SNAPSHOT` targeted with invalid id.
3. `START_SNAPSHOT` active mode with omitted id.
4. `API_CALL` success and failure cases across multiple HTTP methods.
5. Request correlation correctness via `requestId`.

Repo checks:

- `pnpm build`
- `pnpm build:firefox`
