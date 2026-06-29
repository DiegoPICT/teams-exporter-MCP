# MCP Wrapper Implementation Plan

## Document Status

- Status: canonical implementation plan
- Scope: MCP wrapper only
- Bridge constraint: bridge runtime and contracts are established for this iteration; no bridge code changes

## Current Implementation State (2026-06-29)

Implemented now:

- Phase A foundation is in place:
  - MCP lifecycle baseline (`initialize`, `notifications/initialized`)
  - protocol version negotiation and session header enforcement
  - `tools/list` and `tools/call` transport flow
  - Streamable HTTP single endpoint shape (`POST` with `GET` returning `405`)
- Wrapper-managed stack supervision is in place:
  - wrapper can attach to an already-running bridge
  - wrapper can launch bridge as a subprocess when unavailable
  - wrapper tracks bridge runtime state and can auto-restart on crash
- Implemented MCP tools currently available:
  - `wrapper_status` (smoke/status)
  - `snapshot_current_chat` (returns terminal summary including first/last message)
- Initial automated tests exist for lifecycle and HTTP transport baseline.

Not implemented yet (planned next):

- Phase B business tools:
  - `list_conversations`
  - `cancel_snapshot`
  - `teams_api_call`
- Remaining Phase C scope:
  - `snapshot_chat_by_id`
  - protocol-level progress notifications for long-running operations
  - cancellation relay behavior for MCP `notifications/cancelled`
- Planned module decomposition still pending:
  - `mcp_wrapper/bridge_client.py`
  - `mcp_wrapper/streaming.py`
  - `mcp_wrapper/errors.py`
  - `mcp_wrapper/models.py`

## 1) Purpose and Constraints

This repository now treats MCP as the primary consumer-facing interface. The MCP wrapper must expose bridge business capabilities while preserving strict architectural boundaries.

Bridge behavior and contracts remain documented in:

- `docs/architecture.md`
- `docs/northbound-api.md`
- `docs/southbound-protocol.md`
- `docs/companion-project.md`

This plan only defines wrapper-side implementation.

## 2) Non-Negotiable Layering Contract

The MCP wrapper is a northbound adapter over bridge HTTP/SSE.

The wrapper must not:

- import or call bridge internals (`service.py`, `southbound.py`, frame helpers)
- duplicate bridge protocol/state semantics
- reimplement extension operation coordination

The wrapper may only call bridge endpoints already defined in `docs/northbound-api.md`.

## 3) Normative MCP Baseline

Wrapper implementation must follow the MCP specification (current authoritative baseline as of this plan):

- protocol baseline: `2025-06-18`
- lifecycle and capability negotiation
- streamable HTTP transport semantics
- tools contract and error model
- progress and cancellation utilities

If a newer official MCP version is adopted, the wrapper should negotiate it during initialization and maintain compatibility with supported versions.

## 4) Transport Decision and Server Shape

### 4.1 First Delivery Transport

Initial transport is MCP Streamable HTTP to support cross-environment usage (for example, bridge + wrapper in WSL, MCP client on Windows).

### 4.2 Required Streamable HTTP Semantics

The wrapper server must implement MCP transport rules, including:

- one MCP endpoint path supporting `POST` and `GET`
- JSON-RPC 2.0 request/response/notification messages
- content negotiation for `application/json` and `text/event-stream`
- `MCP-Protocol-Version` handling after initialization
- optional `Mcp-Session-Id` session flow if session mode is enabled

### 4.3 Local-Only Defaults

- bind localhost by default
- no remote exposure by default
- document explicit operator steps if non-local binding is required

## 5) Lifecycle and Capability Plan

The wrapper must implement full MCP lifecycle:

1. `initialize` handling with protocol version negotiation
2. declared server capabilities in initialize result
3. transition to operation phase only after `notifications/initialized`

Planned server capabilities:

- required: `tools`
- optional in v1: `resources`, `logging`
- optional/future: `prompts`, `completions`

`tools.listChanged` should be set based on whether tool registration is static or runtime-dynamic.

## 6) MCP v1 Business Tool Scope

### 6.1 Required Business Tools

- `list_conversations`
- `snapshot_current_chat`
- `snapshot_chat_by_id`
- `cancel_snapshot`
- `teams_api_call`

### 6.2 Secondary Operational Surface

Potential secondary capability after required tools are stable:

- `bridge_status`
- `extension_health`
- `extension_logs`

Read-only operational data should be considered as resources first when client UX supports resources well.

## 7) Tool Contract Strategy

### 7.1 Intent-Based Naming

Tool names should express user intent, not raw bridge endpoint names.

Examples:

- `snapshot_current_chat` -> `POST /snapshots` without `conversationId`
- `snapshot_chat_by_id` -> `POST /snapshots` with `conversationId`

### 7.2 Thin and Non-Duplicative Outputs

Wrapper output should be stable but thin:

- preserve bridge payload fidelity where possible
- avoid deep schema remapping of conversation/message domain models
- include operation correlation metadata (`requestId`)

### 7.3 JSON Schema Requirements

For each MCP tool definition:

- provide `inputSchema`
- provide `outputSchema` for structured outputs when practical

If `outputSchema` is declared, wrapper responses must conform.

## 8) Draft Tool Schemas (v1 Targets)

These are target contracts for MCP tool definitions.

`list_conversations`

- Input:
  - optional `includeFolders` (boolean, default `true`)
- Output:
  - `requestId` (string | null)
  - `conversations` (array<object>)
  - `folders` (array<object>, optional)
  - `raw` (object, optional)

`snapshot_current_chat`

- Input:
  - optional `startAt` (RFC3339 timestamp)
  - optional `endAt` (RFC3339 timestamp)
  - optional `includeReplies` (boolean)
  - optional `includeReactions` (boolean)
  - optional `includeSystem` (boolean)
- Output (terminal structured result):
  - `requestId` (string)
  - `status` (`done` | `error` | `cancelled`)
  - `summary` (object)
  - `rawTerminal` (object)

`snapshot_chat_by_id`

- Input:
  - `conversationId` (string, required)
  - optional snapshot flags from `snapshot_current_chat`
- Output:
  - same shape as `snapshot_current_chat`
- Additional mapped error:
  - `TARGET_MISMATCH` when surfaced by bridge

`cancel_snapshot`

- Input:
  - `requestId` (string, required)
- Output:
  - `requestId` (string)
  - `status` (`sent` | `already_terminal`)
  - `raw` (object, optional)

`teams_api_call`

- Input:
  - `method` (string, required)
  - `endpoint` (string, required)
  - optional `query` (object)
  - optional `body` (object)
- Output:
  - `requestId` (string | null)
  - `status` (integer)
  - `data` (string | object | null)
  - `error` (object | null)
  - `raw` (object, optional)

Cross-tool guidance:

- return structured content for machine readability
- optionally include text summary content for compatibility
- surface `requestId` when available

## 9) Progress and Streaming Strategy

Snapshot operations are long-running and should use MCP progress semantics.

Plan:

- client request includes progress token when supported
- wrapper emits `notifications/progress` updates during snapshot lifecycle
- progress updates map bridge SSE events (`SNAPSHOT_STARTED`, `CHUNK`, `DONE`/`ERROR`) into monotonic progress state
- final tool response remains a single terminal tool result

Do not rely on custom non-standard tool event channels as the primary mechanism.

## 10) Cancellation Strategy

Two cancellation paths must coexist:

1. MCP protocol cancellation (`notifications/cancelled`) for in-flight tool calls
2. Business tool cancellation (`cancel_snapshot`) for explicit user intent

Mapping rule for in-flight snapshots:

- on MCP cancellation, wrapper should relay bridge cancel where applicable
- wrapper should stop further processing and free resources
- wrapper must handle cancellation races safely

## 11) Error Handling Model

Use both MCP error layers correctly:

- protocol/JSON-RPC errors for invalid method, invalid params, malformed requests, and transport/lifecycle failures
- tool execution errors for business/runtime failures in otherwise valid tool calls

Bridge-originating error codes to preserve and map consistently:

- `BUSY`
- `CONTEXT_LOST`
- `DISCONNECTED`
- `TIMEOUT`
- `UNSUPPORTED`
- `TARGET_MISMATCH` (targeted snapshot path)

Error responses should preserve upstream details without leaking sensitive content.

## 12) Diagnostics Surface Decision

Operational data (`bridge_status`, `extension_health`, `extension_logs`) should be exposed with minimal duplication.

Decision order:

1. if client supports resources well, expose read-only diagnostics as resources
2. otherwise expose as secondary tools with strict read-only behavior

This keeps business tools primary and diagnostics available without expanding core surface unnecessarily.

## 13) Security and Trust Controls

Wrapper must follow MCP transport security guidance and repository local-only posture.

Required controls:

- validate `Origin` on Streamable HTTP requests
- bind localhost by default
- add configurable authentication boundary when non-local access is intentionally enabled
- do not log raw sensitive chat content by default
- sanitize diagnostic and error payload logging

## 14) Proposed Wrapper Module Layout

- `mcp_wrapper/server.py` - MCP lifecycle, transport endpoint, capability declaration
- `mcp_wrapper/config.py` - configuration and startup validation
- `mcp_wrapper/bridge_client.py` - bridge HTTP/SSE client
- `mcp_wrapper/tools.py` - tool handlers
- `mcp_wrapper/streaming.py` - SSE-to-progress translation and lifecycle helpers
- `mcp_wrapper/errors.py` - protocol/tool error mapping utilities
- `mcp_wrapper/models.py` - JSON-schema-aligned input/output models

Test layout:

- `tests/mcp_wrapper/test_lifecycle.py`
- `tests/mcp_wrapper/test_transport_http.py`
- `tests/mcp_wrapper/test_tools.py`
- `tests/mcp_wrapper/test_streaming_progress.py`
- `tests/mcp_wrapper/test_cancellation.py`
- `tests/mcp_wrapper/test_errors.py`

## 15) Phased Delivery Plan

### Phase A - Protocol Foundation

Deliver:

- MCP lifecycle and capability negotiation
- Streamable HTTP endpoint semantics
- protocol version handling
- base config and logging

Exit criteria:

- compliant initialize/initialized flow
- successful `tools/list` and `tools/call` for a minimal smoke tool

### Phase B - Core Business Tools (Non-Streaming)

Deliver:

- `list_conversations`
- `cancel_snapshot`
- `teams_api_call`
- stable tool schemas and error mapping

Exit criteria:

- deterministic behavior for success and mapped failures

### Phase C - Snapshot Tools with Progress

Deliver:

- `snapshot_current_chat`
- `snapshot_chat_by_id`
- SSE-to-progress updates
- cancellation relay and race-safe cleanup

Exit criteria:

- long-running operations emit coherent progress and deterministic terminal result

### Phase D - Diagnostics Surface

Deliver:

- secondary diagnostics exposure as resources or tools (per decision in Section 12)

Exit criteria:

- read-only diagnostics available with bounded/sanitized output

### Phase E - Hardening and Release Readiness

Deliver:

- protocol conformance checks
- integration validation against running bridge + companion extension
- operator runbook for WSL/Windows local deployment

Exit criteria:

- stable behavior across expected happy/error/cancel paths

## 16) Test and Verification Strategy

### 16.1 Protocol Conformance Tests

- initialize/version negotiation paths
- capability declarations
- Streamable HTTP request/response behavior
- protocol-level cancellation behavior

### 16.2 Tool Contract Tests

- `inputSchema` validation paths
- `outputSchema` conformance (where declared)
- tool result error handling (`isError` semantics)

### 16.3 Integration Tests

- wrapper against real bridge runtime
- business tool happy paths
- mapped failure scenarios (`BUSY`, `DISCONNECTED`, `CONTEXT_LOST`, timeout, `TARGET_MISMATCH`)
- snapshot progress and terminal outcomes

### 16.4 Manual Smoke

- MCP client invokes all required business tools
- snapshot tools produce useful incremental progress and deterministic completion
- API wrapper preserves upstream status/data/error shape

## 17) Risks and Mitigations

- Transport drift from MCP semantics:
  - mitigate with protocol conformance tests and explicit transport checklist
- Bridge/extension behavioral drift:
  - mitigate with compatibility notes and integration smoke gates
- Over-normalization in wrapper:
  - mitigate by preserving payload fidelity and avoiding deep domain remapping

## 18) Out of Scope (This Iteration)

- bridge runtime/protocol redesign
- bridge core concurrency model changes
- bridge authentication redesign
- remote multi-tenant deployment architecture

## 19) Definition of Done

MCP wrapper delivery is complete when:

- required business tools are implemented with documented MCP schemas
- wrapper satisfies MCP lifecycle and Streamable HTTP baseline behavior
- snapshot tools provide progress updates and deterministic terminal outcomes
- cancellation and error mapping are robust and tested
- architecture boundaries are preserved (wrapper only calls bridge northbound API)
- integration and manual smoke criteria pass
