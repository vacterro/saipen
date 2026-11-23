"""T-1684: shared operand roles preserve controls and their capability gates."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import command_effects as effects  # noqa: E402
from saipen_engine import commands, response_surface as response  # noqa: E402
from saipen_engine.host_authority_client import set_authority_mode  # noqa: E402
from saipen_engine.process_tree import run as run_owned  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class RealCLIValues(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-t1631-values-")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / "home"
        self.home.mkdir()
        set_authority_mode("strict", self.home)
        self.project = fresh_project()
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith("SAIPEN_") and key != "CLAUDE_CONFIG_DIR"
        }
        # --home describes admission; Path.home() also selects the service
        # endpoint. Both must name this fixture, including on Windows.
        self.env.update(HOME=str(self.home), USERPROFILE=str(self.home),
                        HOMEDRIVE="", HOMEPATH="", CLAUDE_CONFIG_DIR="")

    def invoke(self, *args: str, source: str | None = None, json_output: bool = True):
        return run_owned(
            [sys.executable, "-B", str(TOOLS / "saipen.py"),
             "--project-root", str(self.project), *(["--json"] if json_output else []), *args],
            cwd=ROOT, env=self.env, input=source, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=45,
        )

    def admit(self, value: str, *, flag: str = "--model"):
        observed = {"--session": "fixture-session", "--model": "ordinary-model",
                    "--event-cwd": str(self.project)}
        observed[flag] = value
        proc = self.invoke(
            "admission", "establish", "--host", "claude", "--session", observed["--session"],
            "--model", observed["--model"], "--home", str(self.home),
            "--runtime", str(self.home / "unserved-runtime"),
            "--authority-root", str(ROOT), "--event-cwd", observed["--event-cwd"],
        )
        self.assertTrue(proc.stdout.lstrip().startswith("{"), proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1, payload)
        self.assertIn("state", payload)
        self.assertNotEqual(payload.get("state"), "UNBOUND", payload)
        self.assertFalse(payload.get("permitted"), payload)
        return payload

    def test_model_spelling_project_root_keeps_strict_binding(self):
        ordinary = self.admit("ordinary-model")
        literal = self.admit("--project-root=" + str(self.home / "missing-project"))
        self.assertEqual((literal["state"], literal["code"]),
                         (ordinary["state"], ordinary["code"]))

    def test_model_spelling_json_flag_is_a_value(self):
        self.admit("--json")

    def test_json_value_does_not_enable_json_output(self):
        proc = self.invoke(
            "admission", "establish", "--session", "fixture-session", "--host", "claude",
            "--model", "--json", "--home", str(self.home),
            "--runtime", str(self.home / "unserved-runtime"),
            "--authority-root", str(ROOT), "--event-cwd", str(self.project),
            json_output=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertFalse(proc.stdout.lstrip().startswith("{"), proc.stdout)

    def test_verify_value_does_not_enable_dry_run(self):
        proc = self.invoke("ticket", "add", "P3", "Option value probe", "--verify", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        board = (self.project / ".saipen/BOARD.md").read_text(encoding="utf-8")
        self.assertIn("Option value probe", board)
        self.assertIn("verify: --dry-run", board)

    def test_verify_help_is_literal_proof_text(self):
        proc = self.invoke("ticket", "add", "P3", "Literal help proof", "--verify", "--help")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["code"], "TICKET_ADDED")
        board = (self.project / ".saipen/BOARD.md").read_text(encoding="utf-8")
        self.assertIn("verify: --help", board)

    def test_verify_boundary_is_literal_proof_text(self):
        proc = self.invoke("ticket", "add", "P3", "Literal boundary proof", "--verify", "--")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["code"], "TICKET_ADDED")
        board = (self.project / ".saipen/BOARD.md").read_text(encoding="utf-8")
        self.assertIn("Literal boundary proof | verify: --\n", board)
        # The actual boundary after a complete option keeps its meaning.
        proc = self.invoke("ticket", "add", "P3", "Real boundary",
                           "--verify", "proof", "--", "tail")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        board = (self.project / ".saipen/BOARD.md").read_text(encoding="utf-8")
        self.assertIn("Real boundary tail | verify: proof\n", board)

    def test_host_entry_runs_the_command_after_the_actual_boundary(self):
        proc = self.invoke("host", "entry", "--host", "--", "--", "status", json_output=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("phase:", proc.stdout)

    def test_literal_help_does_not_grant_write_in_readonly_session(self):
        self.env["SAIPEN_CAPABILITY"] = "read-only"
        board = self.project / ".saipen/BOARD.md"
        before = board.read_bytes()
        proc = self.invoke("ticket", "add", "P3", "Literal help proof", "--verify", "--help")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["code"], "CAPABILITY_DENIED")
        self.assertEqual(board.read_bytes(), before)

    def test_model_spelling_help_flag_is_a_value(self):
        self.admit("--help")

    def test_model_spelling_agent_flag_is_a_value(self):
        self.admit("--agent=unrelated-seat")

    def test_model_spelling_boundary_is_a_value(self):
        self.admit("--")

    def test_model_spelling_compound_separator_is_a_value(self):
        self.admit("+")

    def test_session_spelling_project_root_keeps_strict_binding(self):
        self.admit("--project-root=" + str(self.home / "missing-project"), flag="--session")

    def test_event_cwd_spelling_project_root_does_not_hide_project(self):
        self.admit("--project-root=" + str(self.home / "missing-project"), flag="--event-cwd")

    def test_response_request_spelling_dry_run_reaches_real_checker(self):
        status = self.invoke("status")
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        facts = json.loads(status.stdout)
        digest = response.render_boundary(
            response.OperationalBoundary(
                facts["phase"], "Kontroll tehtud.", "NONE", "NONE", "NONE",
                facts["conformance_status"]["status"],
            )
        )
        ordinary = self.invoke("response", "check", "--stdin", "--request",
                               "ordinary request", source=digest)
        literal = self.invoke("response", "check", "--stdin", "--request",
                              "--dry-run", source=digest)
        self.assertEqual(ordinary.returncode, 0, ordinary.stdout + ordinary.stderr)
        self.assertEqual(literal.returncode, 0, literal.stdout + literal.stderr)
        self.assertEqual(json.loads(literal.stdout), json.loads(ordinary.stdout))


class StructuralValues(unittest.TestCase):
    def test_compound_separator_and_boundary_operands_stay_literal(self):
        self.assertEqual(commands.split_cli_compound_argv(
            ["response", "check", "--request", "+", "+", "status"]),
            [["response", "check", "--request", "+"], ["status"]])
        self.assertEqual(commands.split_cli_compound_argv(
            ["response", "check", "--request", "--", "+", "status"]),
            [["response", "check", "--request", "--"], ["status"]])

    def test_help_value_does_not_change_execution_effect(self):
        self.assertEqual(effects.classify_invocation(
            "admission", ["establish", "--model", "--help"]), effects.EXECUTION)
        self.assertEqual(effects.classify_invocation(
            "admission", ["establish", "--model", "ordinary", "--help"]), effects.DIAGNOSTIC)

    def test_wrapped_command_starts_after_actual_boundary(self):
        self.assertEqual(effects.classify_invocation(
            "host", ["entry", "--host", "--", "--", "ticket", "done", "T-1"]),
            effects.EXECUTION)


if __name__ == "__main__":
    unittest.main()
