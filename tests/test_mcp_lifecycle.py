import unittest
import os

from fastapi.testclient import TestClient

os.environ["MCP_MANAGE_BRIDGE"] = "0"

from mcp_wrapper.server import app


class McpLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def _initialize(self) -> tuple[str, str]:
        response = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "0.0.1",
                    },
                },
            },
        )
        self.assertEqual(200, response.status_code)
        session_id = response.headers.get("Mcp-Session-Id")
        self.assertIsNotNone(session_id)
        payload = response.json()
        negotiated = payload["result"]["protocolVersion"]
        return session_id, negotiated

    def test_initialize_returns_capabilities_and_session(self) -> None:
        session_id, negotiated = self._initialize()
        self.assertTrue(session_id)
        self.assertEqual("2025-06-18", negotiated)

    def test_initialized_notification_marks_session_ready(self) -> None:
        session_id, negotiated = self._initialize()
        response = self.client.post(
            "/mcp",
            headers={
                "Mcp-Session-Id": session_id,
                "MCP-Protocol-Version": negotiated,
            },
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
        )
        self.assertEqual(202, response.status_code)

    def test_request_before_initialized_returns_error(self) -> None:
        session_id, negotiated = self._initialize()
        response = self.client.post(
            "/mcp",
            headers={
                "Mcp-Session-Id": session_id,
                "MCP-Protocol-Version": negotiated,
            },
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )
        self.assertEqual(400, response.status_code)
        payload = response.json()
        self.assertEqual(-32002, payload["error"]["code"])
