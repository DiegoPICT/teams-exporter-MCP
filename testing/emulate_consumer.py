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


def run_list(base: str, timeout: float) -> None:
    status, body = request_json("GET", f"{base}/conversations", timeout=timeout)
    print(f"[consumer] GET /conversations -> {status} {body}")


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
    parser.add_argument("--mode", choices=["status", "list", "snapshot", "cancel", "all"], default="all")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base = base_url(args.host, args.port)

    status, health = request_json("GET", f"{base}/health", timeout=args.timeout)
    print(f"[consumer] GET /health -> {status} {health}")
    status, bridge_status = request_json("GET", f"{base}/bridge/status", timeout=args.timeout)
    print(f"[consumer] GET /bridge/status -> {status} {bridge_status}")

    if args.mode in {"status"}:
        return
    if args.mode in {"list", "all"}:
        run_list(base, timeout=args.timeout)
    if args.mode in {"snapshot", "all"}:
        run_snapshot(base, timeout=args.timeout, events_timeout=args.events_timeout)
    if args.mode in {"cancel", "all"}:
        run_cancel(base, timeout=args.timeout, cancel_delay=args.cancel_delay, events_timeout=args.events_timeout)


if __name__ == "__main__":
    main()
