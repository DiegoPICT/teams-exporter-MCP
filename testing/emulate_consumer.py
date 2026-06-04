#!/usr/bin/env python3
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
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
                print(
                    f"[consumer] sse type={payload.get('type')} requestId={payload.get('requestId')} payload={payload.get('payload')}"
                )
                if payload.get("type") in {"DONE", "ERROR"}:
                    break
            if time.time() - start > max_seconds:
                break

    return events


def base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def extract_title(item: dict[str, Any]) -> str | None:
    for key in ("title", "conversationTitle", "displayName", "name", "topic", "chatName"):
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


def run_list(base: str, timeout: float) -> None:
    status, body = request_json("GET", f"{base}/conversations", timeout=timeout)
    print(f"[consumer] GET /conversations -> {status} {body}")
    if status == 200 and isinstance(body, dict):
        conversations = body.get("conversations") if isinstance(body.get("conversations"), list) else []
        if not conversations:
            print("[consumer] chats: none returned")
            return
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


def run_snapshot(base: str, timeout: float, events_timeout: float) -> None:
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
    print(f"[consumer] POST /snapshots -> {status} {body}")
    if status != 200 or not isinstance(body, dict):
        return

    request_id = body.get("requestId")
    if not isinstance(request_id, str):
        return

    consume_sse(f"{base}/snapshots/{urllib.parse.quote(request_id)}/events", timeout=timeout, max_seconds=events_timeout)


def run_cancel(base: str, timeout: float, cancel_delay: float, events_timeout: float) -> None:
    status, body = request_json("POST", f"{base}/snapshots", payload={}, timeout=timeout)
    print(f"[consumer] POST /snapshots -> {status} {body}")
    if status != 200 or not isinstance(body, dict):
        return

    request_id = body.get("requestId")
    if not isinstance(request_id, str):
        return

    time.sleep(cancel_delay)
    cancel_status, cancel_body = request_json(
        "POST",
        f"{base}/snapshots/{urllib.parse.quote(request_id)}/cancel",
        timeout=timeout,
    )
    print(f"[consumer] POST /snapshots/{request_id}/cancel -> {cancel_status} {cancel_body}")
    consume_sse(f"{base}/snapshots/{urllib.parse.quote(request_id)}/events", timeout=timeout, max_seconds=events_timeout)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emulate northbound consumer behavior over HTTP endpoints")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--events-timeout", type=float, default=30.0)
    parser.add_argument("--cancel-delay", type=float, default=1.0)
    parser.add_argument("--wait-for-extension", type=float, default=0.0, help="Seconds to wait for extension socket")
    parser.add_argument("--mode", choices=["status", "list", "chats", "snapshot", "cancel", "all"], default="all")
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
    print(f"[consumer] GET /health -> {status} {health}")
    status, bridge_status = request_json("GET", f"{base}/bridge/status", timeout=args.timeout)
    print(f"[consumer] GET /bridge/status -> {status} {bridge_status}")

    wait_for_extension(base, timeout=args.timeout, wait_seconds=args.wait_for_extension)

    if args.mode in {"status"}:
        return
    if args.mode in {"list", "chats", "all"}:
        run_list(base, timeout=args.timeout)
    if args.mode in {"snapshot", "all"}:
        run_snapshot(base, timeout=args.timeout, events_timeout=args.events_timeout)
    if args.mode in {"cancel", "all"}:
        run_cancel(base, timeout=args.timeout, cancel_delay=args.cancel_delay, events_timeout=args.events_timeout)


if __name__ == "__main__":
    main()
