#!/usr/bin/env python3
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 10.0) -> tuple[int, Any]:
    data: bytes | None = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed = json.loads(body) if body else {"error": exc.reason}
        return exc.code, parsed


def consume_sse(url: str, timeout: float, max_seconds: float) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    req = urllib.request.Request(url=url, method="GET", headers={"Accept": "text/event-stream"})
    start = time.time()

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line or line.startswith(":"):
                if time.time() - start > max_seconds:
                    break
                continue
            if line.startswith("data: "):
                payload = json.loads(line[len("data: ") :])
                events.append(payload)
                if payload.get("type") == "CHUNK":
                    messages = payload.get("payload", {}).get("messages", [])
                    print(f"[consumer] sse type=CHUNK messages={len(messages)}")
                    for msg in messages:
                        author = msg.get("author") or msg.get("from") or "Unknown"
                        text = msg.get("text") or msg.get("content") or "<no text>"
                        ts = msg.get("ts") or msg.get("timestamp") or msg.get("createdDateTime") or ""
                        print(f"  [{ts}] {author}: <message with {len(text)} characters>")
                else:
                    payload_data = payload.get('payload')
                    if payload.get("type") == "ERROR":
                        error_msg = payload.get("error", "Unknown error")
                        error_code = payload_data.get("code", "UNKNOWN") if isinstance(payload_data, dict) else "UNKNOWN"
                        print(f"\n[consumer] 🛑 Gracefully stopping - Extension reported error: [{error_code}] {error_msg}\n")
                    elif payload_data is not None:
                        print(f"[consumer] sse type={payload.get('type')} requestId={payload.get('requestId')} payload_keys={list(payload_data.keys()) if isinstance(payload_data, dict) else type(payload_data)}")
                    else:
                        print(f"[consumer] sse type={payload.get('type')} requestId={payload.get('requestId')}")
                
                if payload.get("type") in {"DONE", "ERROR"}:
                    if payload.get("type") == "DONE":
                        print(f"\n[consumer] ✅ Stream completed successfully.\n")
                    break
            if time.time() - start > max_seconds:
                break

    return events


def base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def extract_title(item: dict[str, Any]) -> str | None:
    for key in ("title", "conversationTitle", "displayName", "name", "topic", "chatName", "subtitle"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    participants = item.get("participants")
    if isinstance(participants, list):
        names: list[str] = []
        for participant in participants:
            if isinstance(participant, dict):
                candidate = participant.get("displayName") or participant.get("name")
                if isinstance(candidate, str) and candidate.strip():
                    names.append(candidate.strip())
        if names:
            return ", ".join(names)

    group_members = item.get("groupMembers")
    if isinstance(group_members, list):
        names: list[str] = []
        for member in group_members:
            if isinstance(member, str) and member.strip():
                names.append(member.strip())
            elif isinstance(member, dict):
                candidate = (
                    member.get("displayName")
                    or member.get("name")
                    or member.get("title")
                    or member.get("upn")
                )
                if isinstance(candidate, str) and candidate.strip():
                    names.append(candidate.strip())
        if names:
            return ", ".join(names)

    return None


def run_list(base: str, timeout: float) -> list[dict[str, Any]]:
    status, body = request_json("GET", f"{base}/conversations", timeout=timeout)
    body_summary = f"<dict with keys: {list(body.keys())}>" if isinstance(body, dict) else type(body)
    print(f"[consumer] GET /conversations -> {status} {body_summary}")
    if status == 200 and isinstance(body, dict):
        conversations = body.get("conversations") if isinstance(body.get("conversations"), list) else []
        if not conversations:
            print("[consumer] chats: none returned")
            return []
        print("[consumer] chats:")
        missing_title_seen = False
        for idx, item in enumerate(conversations, start=1):
            if isinstance(item, dict):
                conv_id = item.get("id") or item.get("conversationId")
                title = extract_title(item)
                print(f"  {idx}. title={title} id={conv_id}")
                if title is None and not missing_title_seen:
                    missing_title_seen = True
                    print(f"  [debug] missing-title sample keys={sorted(item.keys())}")
                    debug_subset = {
                        key: item.get(key)
                        for key in ("name", "title", "conversationTitle", "displayName", "chatName", "groupMembers")
                        if key in item
                    }
                    print(f"  [debug] missing-title sample values={debug_subset}")
        return conversations
    return []


def run_active_chat(base: str, timeout: float, events_timeout: float) -> None:
    print(f"\n[consumer] >>> Test 1: Iterate messages on the CURRENTLY SELECTED chat <<<\n")
    status, body = request_json(
        "POST",
        f"{base}/snapshots",
        payload={
            "includeReplies": True,
            "includeReactions": True,
            "includeSystem": False,
        },
        timeout=timeout,
    )
    body_summary = f"<dict with keys: {list(body.keys())}>" if isinstance(body, dict) else type(body)
    print(f"[consumer] POST /snapshots (no conversationId) -> {status} {body_summary}")
    if status != 200 or not isinstance(body, dict):
        print(f"[consumer] Failed to start snapshot: {body}")
        return

    request_id = body.get("requestId")
    if not isinstance(request_id, str):
        return

    consume_sse(f"{base}/snapshots/{urllib.parse.quote(request_id)}/events", timeout=timeout, max_seconds=events_timeout)


def run_specific_chat(base: str, timeout: float, events_timeout: float, chat_index: int) -> None:
    print(f"\n[consumer] >>> Test 3: Iterate messages on a SPECIFIC chat <<<\n")
    conversations = run_list(base, timeout=timeout)
    if not conversations:
        print("[consumer] No conversations found, cannot proceed.")
        return
    
    if chat_index < 1 or chat_index > len(conversations):
        print(f"[consumer] Invalid chat index {chat_index}. Must be between 1 and {len(conversations)}.")
        return
    
    selected_chat = conversations[chat_index - 1]
    conv_id = selected_chat.get("id") or selected_chat.get("conversationId")
    title = extract_title(selected_chat) or "Untitled"
    
    print(f"[consumer] Selected chat {chat_index}: {title} ({conv_id})")
    
    status, body = request_json(
        "POST",
        f"{base}/snapshots",
        payload={
            "conversationId": conv_id,
            "includeReplies": True,
            "includeReactions": True,
            "includeSystem": False,
        },
        timeout=timeout,
    )
    body_summary = f"<dict with keys: {list(body.keys())}>" if isinstance(body, dict) else type(body)
    print(f"[consumer] POST /snapshots (with conversationId) -> {status} {body_summary}")
    if status != 200 or not isinstance(body, dict):
        print(f"[consumer] Failed to start snapshot: {body}")
        return

    request_id = body.get("requestId")
    if not isinstance(request_id, str):
        return

    events = consume_sse(f"{base}/snapshots/{urllib.parse.quote(request_id)}/events", timeout=timeout, max_seconds=events_timeout)

    actual_title = title
    actual_conv_id = conv_id
    all_messages = []

    for event in events:
        if event.get("type") == "SNAPSHOT_STARTED":
            payload = event.get("payload", {})
            if payload.get("conversationTitle"):
                actual_title = payload.get("conversationTitle")
            if payload.get("conversationId"):
                actual_conv_id = payload.get("conversationId")
            print(f"[consumer] Stream started for chat: {actual_title} ({actual_conv_id})")
        elif event.get("type") == "CHUNK":
            all_messages.extend(event.get("payload", {}).get("messages", []))

    safe_title = "".join([c if c.isalnum() else "_" for c in actual_title])
    filename = f"{safe_title}.json"

    export_data = {
        "title": actual_title,
        "conversationId": actual_conv_id,
        "messages": all_messages,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(f"\n[consumer] Exported {len(all_messages)} messages to {output_path}")


def run_extension_api_call(
    base: str,
    timeout: float,
    method: str,
    endpoint: str,
    query_json: str | None,
    body_json: str | None,
) -> None:
    payload: dict[str, Any] = {
        "method": method,
        "endpoint": endpoint,
    }

    if query_json:
        try:
            payload["query"] = json.loads(query_json)
        except json.JSONDecodeError:
            print("[consumer] Invalid --api-query JSON")
            return

    if body_json:
        try:
            payload["body"] = json.loads(body_json)
        except json.JSONDecodeError:
            print("[consumer] Invalid --api-body JSON")
            return

    status, body = request_json("POST", f"{base}/extensions/api-call", payload=payload, timeout=timeout)
    print(f"[consumer] POST /extensions/api-call -> {status}")
    if isinstance(body, dict):
        print(f"[consumer] response keys={list(body.keys())}")
    else:
        print(f"[consumer] response type={type(body)}")
    print(f"[consumer] response={body}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emulate northbound consumer behavior over HTTP endpoints")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--events-timeout", type=float, default=30.0)
    parser.add_argument("--wait-for-extension", type=float, default=0.0, help="Seconds to wait for extension socket")
    parser.add_argument("--chat-index", type=int, default=1, help="Index of chat to sync in specific-chat mode (1-based)")
    parser.add_argument("--api-method", default="GET", help="HTTP method for extension-api mode")
    parser.add_argument("--api-endpoint", default="/api/chats", help="Endpoint for extension-api mode")
    parser.add_argument("--api-query", default=None, help="JSON string for API query object")
    parser.add_argument("--api-body", default=None, help="JSON string for API body object")
    parser.add_argument("--mode", choices=["status", "list-chats", "active-chat", "specific-chat", "extension-api"], default="status", help="Operation mode to emulate")
    return parser.parse_args()


def wait_for_extension(base: str, timeout: float, wait_seconds: float) -> None:
    if wait_seconds <= 0:
        return

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        status, payload = request_json("GET", f"{base}/bridge/status", timeout=timeout)
        if status == 200 and isinstance(payload, dict) and payload.get("hasActiveSocket") is True:
            print("[consumer] extension connected")
            return
        time.sleep(0.3)

    print(f"[consumer] extension did not connect within {wait_seconds:.1f}s")


def main() -> None:
    args = parse_args()
    base = base_url(args.host, args.port)

    status, health = request_json("GET", f"{base}/health", timeout=args.timeout)
    print(f"[consumer] GET /health -> {status}")
    status, bridge_status = request_json("GET", f"{base}/bridge/status", timeout=args.timeout)
    bridge_summary = f"<dict with keys: {list(bridge_status.keys())}>" if isinstance(bridge_status, dict) else type(bridge_status)
    print(f"[consumer] GET /bridge/status -> {status} {bridge_summary}")

    wait_for_extension(base, timeout=args.timeout, wait_seconds=args.wait_for_extension)

    if args.mode == "status":
        return
    elif args.mode == "list-chats":
        run_list(base, timeout=args.timeout)
    elif args.mode == "active-chat":
        run_active_chat(base, timeout=args.timeout, events_timeout=args.events_timeout)
    elif args.mode == "specific-chat":
        run_specific_chat(base, timeout=args.timeout, events_timeout=args.events_timeout, chat_index=args.chat_index)
    elif args.mode == "extension-api":
        run_extension_api_call(
            base,
            timeout=args.timeout,
            method=args.api_method,
            endpoint=args.api_endpoint,
            query_json=args.api_query,
            body_json=args.api_body,
        )


if __name__ == "__main__":
    main()
