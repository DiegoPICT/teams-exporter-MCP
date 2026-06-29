# MCP Wrapper Implementation Plan

## Document Status

- Status: canonical planning document
- Scope: MCP wrapper implementation only
- Runtime constraint: bridge protocol/state behavior remains in existing bridge modules

## 1) Why This Plan Exists

The repository now treats MCP as the primary consumer-facing direction. This document defines how to implement that MCP layer without collapsing architecture boundaries.

To avoid duplication, this plan references existing canonical docs for bridge behavior:

- bridge architecture and boundaries: `docs/architecture.md`
- bridge northbound HTTP/SSE surface: `docs/northbound-api.md`
- bridge southbound protocol semantics: `docs/southbound-protocol.md`
- companion extension dependency: `docs/companion-project.md`

This plan does not restate those contracts; it defines wrapper-specific implementation decisions.

## 2) Layering Contract (Non-Negotiable)

The MCP wrapper is a northbound adapter over bridge HTTP/SSE.

The wrapper must not:

- import or call bridge internals (`service.py`, `southbound.py`, frame helpers)
- own extension protocol state semantics
- duplicate bridge operation coordination logic

The wrapper may only call the bridge endpoints documented in `docs/northbound-api.md`.

## 3) Transport Decision

### 3.1 First Delivery Transport

Initial MCP transport target is HTTP listener mode to support cross-environment use (for example, bridge and wrapper in WSL, MCP client on Windows).

### 3.2 Transport Architecture Rule

Tool logic must be transport-agnostic so additional transports can be added later without rewriting business behavior.

### 3.3 Local-Only Safety

Default listener binding remains local-only and should not introduce new remote exposure by default.

## 4) MCP v1 Business Scope

The wrapper should expose business capabilities of the bridge as MCP tools with explicit intent-oriented names.

### 4.1 Required Tools

- `list_conversations`
- `snapshot_current_chat`
- `snapshot_chat_by_id`
- `cancel_snapshot`
- `teams_api_call`

### 4.2 Secondary Operational Tools

These are useful for diagnostics and should be implemented as phase-scoped extras after required tools:

- `bridge_status`
- `extension_health`
- `extension_logs`

## 5) Tool Contract Strategy

### 5.1 Intent-Based Interface

MCP tools should reflect user intent, not raw bridge endpoint names.

Examples:

- `snapshot_current_chat` calls `POST /snapshots` without `conversationId`
- `snapshot_chat_by_id` calls `POST /snapshots` with `conversationId`

### 5.2 Thin, Non-Duplicative Outputs

Wrapper outputs should be stable and minimal while preserving bridge payloads where helpful.

Rules:

- do not create a second deep domain schema for conversation/message models
- avoid lossy transformations of bridge/extension payload content
- include `requestId` and key operation metadata for traceability

### 5.3 Validation Boundaries

Wrapper validates MCP tool input shape only. Bridge and extension remain authoritative for operation/runtime semantics.

## 6) Error Mapping Contract

Centralize error mapping in one module.

Baseline mapping:

- `BUSY` -> conflict/retryable
- `CONTEXT_LOST` -> user action required (reconnect/restore Teams context)
- `DISCONNECTED` -> unavailable (extension not connected)
- `TIMEOUT` -> upstream timeout
- `UNSUPPORTED` -> invalid request/unsupported path
- unknown failures -> adapter error with preserved details

Mapping rules:

- preserve original bridge code, status, message, and request correlation
- provide concise human-actionable guidance
- do not swallow upstream diagnostics

## 7) Snapshot Streaming Behavior

`snapshot_current_chat` and `snapshot_chat_by_id` both use the same streaming pipeline.

Lifecycle:

1. Start snapshot via `POST /snapshots` and capture `requestId`.
2. Open SSE stream via `GET /snapshots/{requestId}/events`.
3. Relay lifecycle events to MCP client with deterministic transitions:
   - `SNAPSHOT_STARTED`
   - zero or more `CHUNK`
   - terminal `DONE` or terminal `ERROR`

Robustness requirements:

- tolerate SSE keepalive comments
- enforce operation timeout and stream-idle timeout with explicit error reasons
- guarantee single terminal outcome per request
- relay caller cancellation to bridge `cancel` path
- clean up in-flight resources on shutdown/interruption

## 8) Proposed Wrapper Module Layout

- `mcp_wrapper/server.py` - MCP server bootstrap and transport wiring
- `mcp_wrapper/config.py` - configuration model and startup validation
- `mcp_wrapper/bridge_client.py` - HTTP/SSE bridge client
- `mcp_wrapper/tools.py` - MCP tool handlers and orchestration
- `mcp_wrapper/streaming.py` - SSE event parser and stream lifecycle helpers
- `mcp_wrapper/errors.py` - canonical error mapping and exception types
- `mcp_wrapper/models.py` - tool input/output models

Test layout:

- `tests/mcp_wrapper/test_tools.py`
- `tests/mcp_wrapper/test_streaming.py`
- `tests/mcp_wrapper/test_errors.py`
- `tests/mcp_wrapper/test_bridge_client.py`

## 9) Phased Delivery Plan

## Phase A - Wrapper Foundation

Deliver:

- package scaffold
- transport bootstrap (HTTP listener)
- config validation
- base logging

Exit criteria:

- wrapper starts cleanly with validated configuration

## Phase B - Core Business Tools (Non-Streaming)

Deliver:

- `list_conversations`
- `cancel_snapshot`
- `teams_api_call`
- centralized error mapper

Exit criteria:

- deterministic request/response behavior and mapped error outcomes

## Phase C - Snapshot Streaming Tools

Deliver:

- `snapshot_current_chat`
- `snapshot_chat_by_id`
- streaming lifecycle handling, timeout handling, cancellation relay

Exit criteria:

- real incremental stream observed on connected extension
- deterministic completion behavior for success, cancel, and failure

## Phase D - Diagnostics Tools

Deliver:

- `bridge_status`
- `extension_health`
- `extension_logs`

Exit criteria:

- useful operational diagnostics without sensitive overexposure in logs

## Phase E - Hardening and Release Readiness

Deliver:

- focused unit/integration coverage
- operator runbook and troubleshooting notes
- compatibility notes for wrapper + bridge + companion extension refs

Exit criteria:

- repeatable local validation and stable behavior under expected failure paths

## 10) Test Strategy

### 10.1 Unit Tests

- tool input validation
- error mapping matrix
- SSE parse and terminal-state handling
- cancellation and timeout behavior

### 10.2 Integration Tests

- wrapper against running bridge
- business tool happy paths
- forced error scenarios: `BUSY`, `DISCONNECTED`, `CONTEXT_LOST`, timeout
- streaming success/cancel/error flows

### 10.3 Manual Smoke

- MCP client invokes each required business tool successfully
- snapshot stream arrives incrementally and terminates deterministically
- API call wrapper returns preserved upstream status/data/error structure

## 11) Security and Data Handling

Wrapper must inherit bridge local-only posture by default.

Guardrails:

- do not log sensitive chat payloads by default
- keep diagnostics output deliberate and bounded
- document that snapshots, logs, and status can contain sensitive metadata/content

## 12) Risks and Mitigations

- Contract drift between bridge and extension:
  - mitigate with compatibility notes and integration smoke gates
- Over-normalization risk in wrapper:
  - mitigate by preserving payload fidelity and avoiding deep schema translation
- Streaming edge cases (disconnect mid-flight):
  - mitigate with strict terminal-state rules and cleanup logic

## 13) Out of Scope

- bridge protocol redesign
- bridge core concurrency model changes
- bridge authentication redesign
- remote multi-tenant deployment model

## 14) Definition of Done

MCP wrapper delivery is complete when:

- all required business tools are implemented and documented
- streaming snapshot tools are robust for success/cancel/failure paths
- error mapping is deterministic and tested
- architecture boundaries remain intact (wrapper only uses bridge northbound API)
- verification suite and manual smoke criteria pass
