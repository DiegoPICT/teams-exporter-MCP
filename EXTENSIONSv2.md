# Extension v2 Recommendations & Discovered Issues

During the implementation and testing of the MCP Bridge (Phases 3 and 4), several behavioral limitations and desync issues were discovered regarding the v1 extension's WebSocket protocol and operation handling. 

This document tracks these discovered issues to provide transparency on current workarounds and to serve as a requirements document for an `EXTENSIONSv2` or a v2 protocol update.

## 1. Ignored `conversationId` during Snapshots (Context-Sync Mismatch)

**Description:**
The bridge protocol design assumes that the extension can export a specific chat if the bridge provides a `conversationId` in the `START_SNAPSHOT` payload. However, the current extension ignores the requested `conversationId`. Instead, it blindly exports the messages from the *currently active chat in the Teams Web GUI* (the active DOM).

This leads to a confusing desync where a consumer requests an export for an older or background chat, but receives the stream for the actively selected chat instead. 

**Log Transparency:**
As seen in the consumer test logs when iterating messages on a specific chat (e.g., selecting the oldest chat, index 687):

```text
[consumer] >>> Test 3: Iterate messages on a SPECIFIC chat <<<
...
[consumer] Selected chat 687: Mission Control Security Gateway (19:e198b3f8f15446f78ec8db0df79afd96@thread.skype)
[consumer] POST /snapshots (with conversationId) -> 200 <dict with keys: ['requestId', 'events']>

[consumer] Stream started for chat: DFT CORE Infra General Chat (19:260d3dd105174c6e8f84a507712f59b8@thread.v2)
[consumer] Exported 327 messages to DFT_CORE_Infra_General_Chat.json
```
*(Notice the requested `19:e198b3f8...` is ignored, and the extension returns `SNAPSHOT_STARTED` for the active `19:260d3dd...` instead).*

**Recommendation for v2:**
- The extension should attempt to switch contexts/DOMs if a specific `conversationId` is requested, OR
- The extension should explicitly reject the `START_SNAPSHOT` command with an `ERROR` (e.g., `code: CONTEXT_MISMATCH`) if the requested `conversationId` does not match the active GUI state, forcing the user to switch chats manually.

## 2. Lack of Auto-Reconnect Mechanism

**Description:**
When the local bridge service restarts (for example, during local development hot-reloads, or a service crash), it gracefully closes the WebSocket with standard close codes like `1012` (Service Restart) or `1001` (Going Away). The extension reflects the "disconnected" state but makes no automatic attempt to reconnect. 

**Log Transparency:**
```text
2026-06-05 15:06:45,395 INFO teams_bridge.bridge event=hello_ack_sent
2026-06-05 15:07:14,343 INFO teams_bridge.service event=extension_frame_received type=CONVERSATIONS request_id=list-8cc527174f
2026-06-05 15:07:28,345 INFO teams_bridge.bridge event=southbound_client_disconnected client=127.0.0.1:64349 code=1012
2026-06-05 15:07:28,447 INFO teams_bridge.bridge event=bridge_stopping
```

**Recommendation for v2:**
- Implement a background reconnect loop in the extension (e.g., exponential backoff up to a maximum interval) when the socket closes with a transient code like `1001`, `1006`, or `1012`. 
- This will drastically improve the user experience for persistent MCP tools, so users don't have to continuously click "Connect MCP" manually if the bridge restarts.

## 3. Lack of Proactive Context Sync (Stale Session Info)

**Description:**
The v1 extension only communicates the active `conversationId` and `conversationTitle` once, during the initial `HELLO` frame. If the user navigates to a different chat in the Teams UI *after* connecting to the bridge, the bridge's `session_info` becomes stale. The bridge is completely blind to this change until an operation fails or exports unexpected data.

**Recommendation for v2:**
- Add a new extension-initiated frame (e.g., `CONTEXT_UPDATED` or `ACTIVE_CHAT_CHANGED`) that is emitted whenever the user changes the active chat in the GUI. 
- The bridge can use this to keep its `session_info` synchronized in real-time, allowing MCP LLM clients to proactively ask "I see you just switched to Chat X, would you like me to summarize it?"

## 4. Extension Internal Log Retrieval for Troubleshooting

**Description:**
Currently, if the extension encounters internal errors (e.g., DOM parsing failures, network drops, internal state errors), the bridge has little to no visibility unless a specifically mapped `ERROR` frame is sent. To aid in autonomous troubleshooting without requiring the user to open browser Developer Tools, the bridge needs a way to fetch recent internal logs directly from the extension.

**Recommendation for v2:**
- Implement a new `GET_LOGS` transaction where the bridge can specify a limit parameter (e.g., `{"limit": 100}`).
- The extension responds with a `LOGS_RESULT` frame containing an array of its recent internal console/log entries (including timestamps, severity levels, and raw messages).
- This will allow the MCP LLM to proactively diagnose extension-side issues and provide actionable advice to the user.

## 5. Generic API Call Pass-Through

**Description:**
The v1 protocol relies on highly specific, rigid operations (`LIST_CONVERSATIONS`, `START_SNAPSHOT`). As the MCP bridge evolves, it will inevitably need access to other data (e.g., user profiles, team channel lists, specific message metadata) that the extension could easily fetch using its authenticated context. Hardcoding every single new operation into the extension protocol creates a tight coupling bottleneck.

**Recommendation for v2:**
- Implement a generic `API_CALL` transaction.
- The bridge sends a frame specifying the exact request parameters: `{"method": "GET", "endpoint": "/api/...", "body": {}}`.
- The extension acts as an authenticated proxy, executes the HTTP request against the internal Teams API, and returns an `API_RESULT` frame containing the resulting raw object, HTTP status code, and/or error details: `{"status": 200, "data": {...}, "error": null}`.
- This creates a highly flexible interface where complex business logic can live entirely in the bridge/MCP layer without requiring constant extension updates.
