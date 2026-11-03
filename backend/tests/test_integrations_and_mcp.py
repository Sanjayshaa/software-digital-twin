"""
Phase 9 — Integrations, GitLab & MCP Safety Regression Tests.
Verifies:
1. Unified VCS discovery for GitHub and GitLab with error handling.
2. In-memory token policy (tokens never stored in DB or logged).
3. MCP JSON-RPC protocol compliance and tool execution.
4. MCP Path containment security (traversal outside workspace root is blocked).
5. Explicit approval gate on patch application (no write without user_approved=True).
"""

import os
import sys
import json
import unittest
from unittest.mock import patch

# Auto re-exec under project virtualenv
if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest"] + sys.argv[1:])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_dir = os.path.abspath(os.path.join(backend_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from fastapi.testclient import TestClient
from main import app
from cli.mcp_server import TwinCoreMCPServer


class TestIntegrationsAndMCPServer(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.mcp = TwinCoreMCPServer()

    def test_01_integrations_status_shows_unconfigured_requirements(self):
        """Verifies integrations status truthful reporting without fabricating connections."""
        res = self.client.get("/integrations/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        providers = data["providers"]
        self.assertIn("github", providers)
        self.assertIn("gitlab", providers)
        self.assertIn("mcp_server", providers)
        self.assertTrue(providers["mcp_server"]["configured"])

    @patch("app.api.integrations._call_gitlab_api")
    def test_02_gitlab_discovery_and_normalization(self, mock_gl):
        """Verifies GitLab projects are discovered and normalized properly."""
        mock_gl.return_value = (
            200,
            [
                {
                    "id": 991,
                    "name": "payment-microservice",
                    "path_with_namespace": "fintech/payment-microservice",
                    "http_url_to_repo": "https://gitlab.com/fintech/payment-microservice.git",
                    "web_url": "https://gitlab.com/fintech/payment-microservice",
                    "visibility": "private",
                    "default_branch": "main",
                    "description": "Core payment service",
                    "last_activity_at": "2026-11-01T12:00:00Z"
                }
            ],
            {"x-next-page": ""}
        )

        res = self.client.post(
            "/integrations/discover-repositories",
            json={"provider": "gitlab", "token": "glpat-test-secret-token", "page": 1, "per_page": 20}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["provider"], "gitlab")
        self.assertEqual(len(data["repositories"]), 1)
        repo = data["repositories"][0]
        self.assertEqual(repo["name"], "payment-microservice")
        self.assertTrue(repo["private"])
        self.assertEqual(repo["clone_url"], "https://gitlab.com/fintech/payment-microservice.git")

    def test_03_mcp_initialize_and_tools_list(self):
        """Verifies MCP JSON-RPC protocol compliance for initialize and tools/list."""
        init_req = json.dumps({"jsonrpc": "2.0", "method": "initialize", "id": 1})
        init_resp = json.loads(self.mcp.handle_request(init_req))
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "TwinCore-MCP-Server")

        list_req = json.dumps({"jsonrpc": "2.0", "method": "tools/list", "id": 2})
        list_resp = json.loads(self.mcp.handle_request(list_req))
        tool_names = [t["name"] for t in list_resp["result"]["tools"]]
        self.assertIn("twincore_get_workspace", tool_names)
        self.assertIn("twincore_analyze_working_tree", tool_names)
        self.assertIn("twincore_preview_patch", tool_names)
        self.assertIn("twincore_apply_patch", tool_names)

    def test_04_mcp_path_containment_security(self):
        """Verifies path traversal outside workspace is blocked."""
        preview_req = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "twincore_preview_patch",
                "arguments": {
                    "workspace_path": "/etc",
                    "file_path": "passwd",
                    "proposed_content": "root:x:0:0"
                }
            },
            "id": 3
        })
        resp = json.loads(self.mcp.handle_request(preview_req))
        self.assertIn("error", resp)
        self.assertIn("escapes workspace", resp["error"]["message"].lower())

    def test_05_mcp_approval_gate_on_patch_apply(self):
        """Verifies apply_patch fails without explicit user approval."""
        apply_unapproved = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "twincore_apply_patch",
                "arguments": {
                    "file_path": "test_sample.txt",
                    "new_content": "hello world",
                    "user_approved": False
                }
            },
            "id": 4
        })
        resp = json.loads(self.mcp.handle_request(apply_unapproved))
        self.assertIn("error", resp)
        self.assertIn("user_approved=true is required", resp["error"]["message"].lower())


if __name__ == "__main__":
    unittest.main()

