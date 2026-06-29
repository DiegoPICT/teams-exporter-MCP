import unittest
import os

from fastapi.testclient import TestClient

os.environ["MCP_MANAGE_BRIDGE"] = "0"

from mcp_wrapper.server import app


class McpTransportHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def _ready_headers(self) -> dict[str, str]:
        init_response = self.client.post(
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
        session_id = init_response.headers["Mcp-Session-Id"]
        protocol = init_response.json()["result"]["protocolVersion"]
        self.client.post(
            "/mcp",
            headers={
                "Mcp-Session-Id": session_id,
                "MCP-Protocol-Version": protocol,
            },
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
        )
        return {
            "Mcp-Session-Id": session_id,
            "MCP-Protocol-Version": protocol,
        }

    def test_get_returns_405(self) -> None:
        response = self.client.get("/mcp")
        self.assertEqual(405, response.status_code)

    def test_requires_session_headers_after_initialize(self) -> None:
        response = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )
        self.assertEqual(400, response.status_code)

    def test_tools_list_and_tools_call_smoke_tool(self) -> None:
        headers = self._ready_headers()

        tools_list = self.client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )
        self.assertEqual(200, tools_list.status_code)
        tools = tools_list.json()["result"]["tools"]
        self.assertEqual("wrapper_status", tools[0]["name"])

        tools_call = self.client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "wrapper_status",
                    "arguments": {},
                },
            },
        )
        self.assertEqual(200, tools_call.status_code)
        payload = tools_call.json()["result"]
        self.assertFalse(payload["isError"])
        self.assertTrue(payload["structuredContent"]["ok"])
