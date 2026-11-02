#!/usr/bin/env python3
"""Fast, dependency-free contracts for the model-facing workshop harness."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HARNESS_ROOT = ROOT / "harness"
if not HARNESS_ROOT.is_dir():
    HARNESS_ROOT = Path("/opt/academy-harness")
TOOLS_PATH = HARNESS_ROOT / "tools.py"

spec = importlib.util.spec_from_file_location("vulnerableapp_harness_tools", TOOLS_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import setup failure
    raise RuntimeError("cannot load harness/tools.py")
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


class HarnessUsabilityTests(unittest.TestCase):
    def test_display_redacts_credentials_but_keeps_benign_arguments(self) -> None:
        value = {
            "username": "student-marker",
            "password": "real-password",
            "Authorization": "Bearer real-token",
            "Cookie": "session=real-cookie",
            "payload": "100 OR 2=2",
            "nested": {"api_key": "real-key", "id": "999"},
        }
        shown = tools._redact_display(value)
        self.assertEqual(shown["username"], "student-marker")
        self.assertEqual(shown["payload"], "100 OR 2=2")
        self.assertEqual(shown["nested"]["id"], "999")
        for key in ("password", "Authorization", "Cookie"):
            self.assertEqual(shown[key], "<redacted>")
        self.assertEqual(shown["nested"]["api_key"], "<redacted>")
        self.assertNotIn("real-token", json.dumps(shown))

    def test_approval_sensitive_text_redaction_contract_is_present(self) -> None:
        # This guards the model-facing approval path without importing the pinned
        # Cordis runtime. The actual sanitizer is exercised by the JS plugin.
        source = (HARNESS_ROOT / "workshop-plugin.mjs").read_text(encoding="utf-8")
        for marker in ("sensitiveApprovalKey", "sanitizeApprovalValue", "Aprobación única", "header_names"):
            self.assertIn(marker, source)
        self.assertIn("Bearer <redacted>", source)

    def test_rejects_unsafe_services_and_headers(self) -> None:
        with self.assertRaises(tools.ToolError):
            tools._validate_discover_args({"service": "127.0.0.1"})
        with self.assertRaises(tools.ToolError):
            tools._validate_string_dict({"Host": "evil.test"}, "request.headers", header=True)
        with self.assertRaises(tools.ToolError):
            tools._validate_string_dict({"X-Test": "ok\r\nInjected: yes"}, "request.headers", header=True)
        with self.assertRaises(tools.ToolError):
            tools._validate_string_dict({"Proxy-Authorization": "secret"}, "request.headers", header=True)

    def test_rejects_arbitrary_and_traversal_catalog_paths(self) -> None:
        for route in (
            "http://evil.test/pwn",
            "http://target:9090/VulnerableApp/a?next=evil",
            "../etc/passwd",
            "safe/%2e%2e/secret",
            "safe//double",
        ):
            with self.subTest(route=route):
                with self.assertRaises(tools.ToolError):
                    tools._normalize_route(route)

    def test_mission_filters_and_pagination_are_bounded(self) -> None:
        with self.assertRaises(tools.ToolError):
            tools._validate_missions_args({"limit": 33})
        with self.assertRaises(tools.ToolError):
            tools._validate_missions_args({"offset": 257})
        with self.assertRaises(tools.ToolError):
            tools._validate_missions_args({"mission_id": "safe-1", "limit": 1})
        with self.assertRaises(tools.ToolError):
            tools._validate_missions_args({"path": "/tmp/catalog.json"})
        self.assertEqual(tools._validate_missions_args({"limit": 2, "offset": 3})[2:], (2, 3))

    def test_catalog_selection_is_exact_and_summary_is_bounded(self) -> None:
        catalog = {
            "version": 1,
            "missions": [
                {
                    "id": "safe-1",
                    "title": "Control local",
                    "family": "demo",
                    "method": "GET",
                    "route": "Demo/LEVEL_1",
                    "params": {"id": "100 OR 2=2"},
                    "headers": {"Accept": "application/json"},
                    "body": None,
                    "content_type": None,
                    "points": 0,
                    "tool": "http_request",
                    "steps": ["curl -i --get http://target:9090/VulnerableApp/Demo/LEVEL_1"],
                    "hints": ["Usa el control"],
                    "expected": "HTTP 200 con evidencia real",
                    "mitigation": "Usa consultas parametrizadas",
                }
            ],
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
            json.dump(catalog, handle)
            handle.flush()
            with patch.object(tools, "CATALOG_PATH", Path(handle.name)):
                result = tools._missions({"mission_id": "safe-1"})
        self.assertEqual(result["mission"]["id"], "safe-1")
        self.assertIn("100 OR 2=2", json.dumps(result, ensure_ascii=False))
        self.assertLessEqual(len(result["summary"].encode()), tools.MAX_MISSION_SUMMARY_BYTES)

    def test_submit_preserves_mission_for_request_summary(self) -> None:
        request={"method":"GET","params":{"id":"2"},"headers":{},"body":None,"content_type":None}
        mission={"id":"safe-1","route":"Demo/LEVEL_1"}
        class Client:
            @staticmethod
            def _api(*args, **kwargs):
                return 200,{"success":True,"awarded":100,"score":100,"evidence":{"content":"fixture"}}
        with patch.object(tools,"_validate_request",return_value=(mission,request)), patch.object(tools,"_check_session"), patch.object(tools,"_load_lab_client",return_value=Client()):
            result=tools._submit({"mission_id":"safe-1","request":request})
        self.assertEqual(result["request_summary"]["route"],"/VulnerableApp/Demo/LEVEL_1")
        self.assertEqual(result["awarded"],100)
        self.assertTrue(result["success"])

    def test_progress_uses_academy_values_and_has_no_local_score_calculation(self) -> None:
        class FakeClient:
            def _api(self, path, method, auth=True, timeout=0):
                self.assert_api(path, method, auth, timeout)
                return 200, {
                    "user": {"id": 7, "username": "student"},
                    "score": 17,
                    "maximum": 100,
                    "completed": ["safe-1"],
                    "events": [{"mission_id": "safe-1", "success": True, "awarded": 17}],
                }

            def assert_api(self, path, method, auth, timeout):
                self.last = (path, method, auth, timeout)

        fake = FakeClient()
        with tempfile.NamedTemporaryFile() as session:
            path = Path(session.name)
            with patch.object(tools, "_session_path", return_value=path), patch.object(tools, "_check_session"), patch.object(tools, "_load_lab_client", return_value=fake):
                result = tools._progress()
        self.assertEqual(result["server"]["score"], 17)
        self.assertEqual(result["server"]["maximum"], 100)
        self.assertIn("score actual reportado por Academy=17", result["summary"])
        self.assertIn("no calcula ni concede XP", result["summary"])


if __name__ == "__main__":
    unittest.main()
