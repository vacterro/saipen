"""T-1631: option values cannot replace binding or activate global switches."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import saipen as cli  # noqa: E402
from test_t1412_conformance_truth import T1412Base  # noqa: E402


class PublicValueOwnership(T1412Base):
    def setUp(self):
        super().setUp()
        self.root = self.make_project("t1631")

    def test_model_value_cannot_turn_a_bound_project_into_unbound(self):
        for mode in ("degraded", "strict"):
            with self.subTest(mode=mode):
                profile = self.base / mode
                (profile / ".saipen").mkdir(parents=True)
                (profile / ".saipen" / "authority.json").write_text(
                    json.dumps({"mode": mode}), encoding="utf-8",
                )
                rc, payload, text = self.run_cli(
                    self.root, "admission", "establish", "--session", "t1631-session",
                    "--host", "claude", "--model", "--project-root=missing-project",
                    "--home", str(profile),
                    "--authority-root", str(self.base / "authority"),
                    "--runtime", str(self.base / "runtime"),
                )
                self.assertIn(rc, (0, 1), text)
                self.assertTrue(payload.get("applies"), text)
                self.assertNotEqual(payload.get("state"), "UNBOUND", text)
                self.assertEqual(payload.get("permitted"), mode == "degraded", text)

    def test_request_values_are_carried_verbatim_through_the_real_cli(self):
        for value in ("--dry-run", "--json", "--project-root=missing-project", "--"):
            with self.subTest(value=value):
                rc, payload, text = self.run_cli(
                    self.root, "response", "policy", "--request", value,
                )
                self.assertEqual(rc, 0, text)
                self.assertEqual(payload.get("code"), "EXECUTION_POLICY", text)

    def test_response_check_receives_the_request_and_original_binding(self):
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("SAIPEN_")}
        for value in ("--dry-run", "--json", "--project-root=missing-project", "--"):
            with self.subTest(value=value):
                result = subprocess.run(
                    [sys.executable, "-B", str(TOOLS / "saipen.py"),
                     "--project-root", str(self.root), "response", "check", "--stdin",
                     "--request", value, "--json"],
                    input="", capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=environment, timeout=120,
                )
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(payload.get("code"), "EXEC_RESPONSE_INVALID", payload)
                self.assertIn("errors", payload, "checker never reached its response oracle")

    def test_an_enqueue_text_body_owns_all_its_words(self):
        body = ("--project-root=missing-project", "--json", "--dry-run", "--", "tail")
        rc, _, output = self.run_cli(
            self.root, "--json", "audit", "enqueue", "--producer", "t1631",
            "--operation-id", "opaque-body", "--text", *body, json_output=False,
        )
        self.assertEqual(rc, 0, output)
        layers = list((self.root / "audit").glob("[0-9]*.md"))
        self.assertEqual(len(layers), 1, output)
        self.assertEqual(layers[0].read_text(encoding="utf-8"), " ".join(body) + "\n")


class DispatchValueOwnership(unittest.TestCase):
    def setUp(self):
        for name in ("_AGENT_OVERRIDE", "_RUNTIME_INFO_OVERRIDE", "_ROUTE_ECHO"):
            patcher = mock.patch.object(cli, name, getattr(cli, name))
            patcher.start()
            self.addCleanup(patcher.stop)

    def invoke(self, arguments, handler):
        with mock.patch.object(cli, handler, return_value=0) as dispatch:
            self.assertEqual(cli.main(arguments), 0)
        return dispatch.call_args.args

    def test_every_host_fact_keeps_global_shaped_values_opaque(self):
        value_flags = (
            "--session", "--admission-session", "--host", "--model", "--provider",
            "--authority-root", "--home", "--event-cwd", "--runtime", "--reason",
        )
        values = (
            "--project-root=foreign", "--agent=foreign", "--runtime-info=missing.json",
            "--dry-run", "--json", "--",
        )
        for flag in value_flags:
            for value in values:
                with self.subTest(flag=flag, value=value):
                    local, as_json, root = self.invoke(
                        ["--project-root", "intended", "admission", "status", flag, value],
                        "_admission_cli",
                    )
                    self.assertEqual(local, ["admission", "status", flag, value])
                    self.assertFalse(as_json)
                    self.assertEqual(root, "intended")
                    self.assertIsNone(cli._AGENT_OVERRIDE)
                    self.assertIsNone(cli._RUNTIME_INFO_OVERRIDE)

    def test_request_cannot_activate_global_transport_or_mode(self):
        for value in ("--json", "--dry-run", "--project-root=foreign"):
            with self.subTest(value=value):
                local, as_json, root = self.invoke(
                    ["--project-root", "intended", "response", "policy", "--request", value],
                    "_response_cli",
                )
                self.assertEqual(local[-2:], ["--request", value])
                self.assertFalse(as_json)
                self.assertEqual(root, "intended")

    def test_real_global_flags_after_values_still_work(self):
        local, as_json, root = self.invoke(
            ["admission", "status", "--fresh", "--model", "--project-root=foreign",
             "--project-root", "intended", "--agent", "operator", "--json"],
            "_admission_cli",
        )
        self.assertEqual(local, ["admission", "status", "--fresh", "--model",
                                 "--project-root=foreign"])
        self.assertTrue(as_json)
        self.assertEqual(root, "intended")
        self.assertEqual(cli._AGENT_OVERRIDE, "operator")

    def test_actual_delimiter_still_ends_global_option_scanning(self):
        local, as_json, root = self.invoke(
            ["--project-root", "intended", "response", "policy", "--",
             "--project-root=foreign", "--json"],
            "_response_cli",
        )
        self.assertEqual(local, ["response", "policy", "--", "--project-root=foreign", "--json"])
        self.assertFalse(as_json)
        self.assertEqual(root, "intended")


if __name__ == "__main__":
    unittest.main()
