import asyncio
import json
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any

from mcp_wrapper.config import McpConfig
from mcp_wrapper.state import BridgeStateStore


class BridgeSupervisor:
    def __init__(self, config: McpConfig, state: BridgeStateStore) -> None:
        self._config = config
        self._state = state
        self._process: subprocess.Popen[bytes] | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()

    def _health_url(self) -> str:
        return f"{self._config.bridge_base_url.rstrip('/')}/health"

    def _status_url(self) -> str:
        return f"{self._config.bridge_base_url.rstrip('/')}/bridge/status"

    def _is_process_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _sync_probe_bridge(self) -> bool:
        req = urllib.request.Request(self._health_url(), method="GET", headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=1.5) as response:
                if response.status != 200:
                    return False
                payload = json.loads(response.read().decode("utf-8"))
                return isinstance(payload, dict) and payload.get("ok") is True
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError, urllib.error.HTTPError):
            return False

    async def probe_bridge(self) -> bool:
        reachable = await asyncio.to_thread(self._sync_probe_bridge)
        if not reachable:
            self._state.mark_unreachable("bridge health probe failed")
        return reachable

    def _launch_process(self, command: Sequence[str]) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            list(command),
            stdout=None,
            stderr=None,
        )

    async def _wait_until_ready(self, timeout_seconds: float) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self._process is not None and self._process.poll() is not None:
                self._state.mark_crashed(self._process.returncode)
                return False
            if await self.probe_bridge():
                self._state.mark_running(self._process.pid if self._process else None, started_by_wrapper=self._process is not None)
                return True
            await asyncio.sleep(0.2)
        self._state.mark_unreachable("bridge startup timeout")
        return False

    async def start(self) -> None:
        async with self._lock:
            if await self.probe_bridge():
                self._state.mark_attached()
                return

            if not self._config.manage_bridge:
                return

            if self._is_process_alive():
                return

            self._state.mark_starting()
            self._process = self._launch_process(self._config.bridge_command)
            ready = await self._wait_until_ready(self._config.bridge_startup_timeout_seconds)
            if not ready:
                await self._terminate_process_locked()
                raise RuntimeError("Bridge failed to start under wrapper supervision")

        self._stop_event.clear()
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _terminate_process_locked(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            self._state.mark_stopped()
            return

        if process.poll() is None:
            process.terminate()
            try:
                await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=self._config.bridge_shutdown_timeout_seconds)
            except asyncio.TimeoutError:
                process.kill()
                await asyncio.to_thread(process.wait)

        self._state.mark_stopped()

    async def stop(self) -> None:
        self._stop_event.set()
        if self._monitor_task is not None:
            await asyncio.gather(self._monitor_task, return_exceptions=True)
            self._monitor_task = None

        async with self._lock:
            await self._terminate_process_locked()

    async def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self._config.bridge_monitor_interval_seconds)
            async with self._lock:
                if self._process is None:
                    continue

                exit_code = self._process.poll()
                if exit_code is None:
                    continue

                self._state.mark_crashed(exit_code)
                self._process = None

                if not self._config.manage_bridge or not self._config.bridge_auto_restart:
                    continue

                self._state.increment_restart()
                self._state.mark_starting()
                self._process = self._launch_process(self._config.bridge_command)
                ready = await self._wait_until_ready(self._config.bridge_startup_timeout_seconds)
                if not ready:
                    await self._terminate_process_locked()

    def snapshot(self) -> dict[str, Any]:
        return self._state.snapshot()
