#!/usr/bin/env python3
import argparse
import json
import subprocess
import threading
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


def wait_for_extension_connected(base: str, timeout: float = 12.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, payload = request_json("GET", f"{base}/bridge/status", timeout=2.0)
        if status == 200 and isinstance(payload, dict) and payload.get("hasActiveSocket") is True:
            return
        time.sleep(0.2)
    raise AssertionError("Extension did not connect in time")


def collect_sse_events(url: str, events: list[dict[str, Any]], stop: threading.Event, timeout: float) -> None:
    req = urllib.request.Request(url=url, method="GET", headers={"Accept": "text/event-stream"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            if stop.is_set():
                return
            line = raw_line.decode("utf-8").strip()
            if not line or line.startswith(":"):
                continue
            if line.startswith("data: "):
                payload = json.loads(line[len("data: ") :])
                events.append(payload)
                print(
                    f"[smoke] sse type={payload.get('type')} requestId={payload.get('requestId')} payload={payload.get('payload')}"
                )
                if payload.get("type") in {"DONE", "ERROR"}:
                    return


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_smoke(host: str, port: int, project_root: Path) -> None:
    base = f"http://{host}:{port}"
    ext_cmd = [
        "python3",
        str(project_root / "testing" / "emulate_extension.py"),
        "--host",
        host,
        "--port",
        str(port),
        "--chunk-delay",
        "1.0",
        "--chunk-count",
        "4",
        "--idle-timeout",
        "45",
    ]

    ext_log = project_root / "log" / "smoke_phase3_extension.log"
    with ext_log.open("w", encoding="utf-8") as ext_out:
        proc = subprocess.Popen(ext_cmd, stdout=ext_out, stderr=subprocess.STDOUT, cwd=project_root)

        try:
            status, health = request_json("GET", f"{base}/health", timeout=3)
            assert_true(status == 200 and isinstance(health, dict) and health.get("ok") is True, "Health endpoint failed")

            wait_for_extension_connected(base)

            status, conversations = request_json("GET", f"{base}/conversations", timeout=10)
            assert_true(status == 200, f"Expected 200 from /conversations, got {status}")
            assert_true(isinstance(conversations, dict), "Conversations payload must be object")
            assert_true(len(conversations.get("conversations", [])) >= 1, "Expected at least one conversation")

            status, snap_start = request_json("POST", f"{base}/snapshots", payload={}, timeout=10)
            assert_true(status == 200 and isinstance(snap_start, dict), "Failed to start snapshot")
            request_id = snap_start.get("requestId")
            assert_true(isinstance(request_id, str), "Snapshot requestId missing")

            busy_status, busy_resp = request_json("GET", f"{base}/conversations", timeout=10)
            assert_true(busy_status == 409, f"Expected BUSY 409 during active snapshot, got {busy_status}")
            assert_true(isinstance(busy_resp, dict), "Busy response must be object")
            detail = busy_resp.get("detail") if isinstance(busy_resp.get("detail"), dict) else {}
            assert_true(detail.get("code") == "BUSY", f"Expected BUSY code, got {detail}")

            events: list[dict[str, Any]] = []
            stop = threading.Event()
            events_url = f"{base}/snapshots/{urllib.parse.quote(request_id)}/events"
            t = threading.Thread(target=collect_sse_events, args=(events_url, events, stop, 60), daemon=True)
            t.start()

            deadline = time.time() + 20
            while time.time() < deadline:
                has_chunk = any(evt.get("type") == "CHUNK" for evt in events)
                if has_chunk:
                    break
                time.sleep(0.2)
            assert_true(any(evt.get("type") == "CHUNK" for evt in events), "Expected at least one CHUNK before cancel")

            cancel_status, cancel_resp = request_json(
                "POST",
                f"{base}/snapshots/{urllib.parse.quote(request_id)}/cancel",
                timeout=10,
            )
            assert_true(cancel_status == 200, f"Expected 200 from cancel endpoint, got {cancel_status}")
            assert_true(isinstance(cancel_resp, dict), "Cancel response must be object")

            t.join(timeout=20)
            stop.set()

            assert_true(any(evt.get("type") == "SNAPSHOT_STARTED" for evt in events), "Expected SNAPSHOT_STARTED event")
            terminal = next((evt for evt in events if evt.get("type") in {"DONE", "ERROR"}), None)
            assert_true(terminal is not None, "Expected terminal event")
            assert_true(terminal.get("type") == "DONE", f"Expected DONE terminal event, got {terminal}")
            terminal_payload = terminal.get("payload") if isinstance(terminal.get("payload"), dict) else {}
            assert_true(terminal_payload.get("cancelled") is True, f"Expected cancelled DONE, got {terminal_payload}")

            print("[ok] Phase 3 smoke checks passed")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3 end-to-end smoke test via northbound + extension emulator")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    run_smoke(host=args.host, port=args.port, project_root=project_root)


if __name__ == "__main__":
    main()
