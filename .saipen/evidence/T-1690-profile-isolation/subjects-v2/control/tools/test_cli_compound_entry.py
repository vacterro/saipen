"""Operator CLI compound dispatch, including the Windows launcher boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for entry in (str(TOOLS), str(ROOT / "bootstrap")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import cli_launcher  # noqa: E402
from saipen_engine.commands import split_cli_compound_argv  # noqa: E402


class DecodedArgvTests(unittest.TestCase):
    def test_matrix_preserves_order_arguments_and_quoted_payload(self):
        cases = (
            ([], [[]]),
            (["status"], [["status"]]),
            (
                ["ticket", "add", "P1", "value with spaces"],
                [["ticket", "add", "P1", "value with spaces"]],
            ),
            (["clean", "+", "status"], [["clean"], ["status"]]),
            (["status", "+", "validate", "+", "status"], [["status"], ["validate"], ["status"]]),
            (["status", "+", "build", "ccc"], [["status"], ["build", "ccc"]]),
            (["push", "+", "build", "ccc"], [["push"], ["build", "ccc"]]),
            (
                ["ticket", "add", "P1", "A + B", "+", "status"],
                [["ticket", "add", "P1", "A + B"], ["status"]],
            ),
            (["status", "--", "+"], [["status", "--", "+"]]),
            (["ticket", "add", "P1", r"\+", "+", "status"],
             [["ticket", "add", "P1", "+"], ["status"]]),
            (["ticket", "add", "P1", "--", r"\+"],
             [["ticket", "add", "P1", "--", r"\+"]]),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(split_cli_compound_argv(argv), expected)

    def test_empty_segments_refuse(self):
        for argv in (["+", "status"], ["status", "+"], ["status", "+", "+", "status"]):
            with self.subTest(argv=argv), self.assertRaisesRegex(ValueError, "empty segment"):
                split_cli_compound_argv(argv)


class CleanSemanticsTests(unittest.TestCase):
    def test_entry_is_pending_and_exit_requires_the_completion_marker(self):
        from test_guard_hostile_matrix import fresh_project

        project = fresh_project()

        def invoke(*args: str) -> dict:
            proc = subprocess.run(
                [sys.executable, str(TOOLS / "saipen.py"), *args,
                 "--project-root", str(project), "--json"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            return json.loads(proc.stdout)

        entered = invoke("clean")
        self.assertEqual(
            (entered["phase"], entered["next_action"], entered["clean_execution"]),
            ("CLEAN", "PHASE CLEAN", "PENDING"),
        )
        self.assertEqual(invoke("status")["clean_execution"], "PENDING")
        invoke("checkpoint", "RUN", "clean -> done @abc123")
        invoke("transition", "DONE", "clean phase completed")
        completed = invoke("status")
        self.assertEqual(completed["phase"], "DONE")
        self.assertEqual(completed["clean_execution"], "COMPLETED")

        without_marker = fresh_project()
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "clean", "--project-root",
             str(without_marker), "--json"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "transition", "DONE",
             "--project-root", str(without_marker), "--json"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "status", "--project-root",
             str(without_marker), "--json"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(json.loads(proc.stdout)["clean_execution"], "UNPROVEN")

    def test_completion_survives_later_checkpoints(self):
        from test_guard_hostile_matrix import fresh_project

        project = fresh_project()

        def invoke(*args: str) -> dict:
            proc = subprocess.run(
                [sys.executable, str(TOOLS / "saipen.py"), *args,
                 "--project-root", str(project), "--json"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            return json.loads(proc.stdout)

        invoke("clean")
        invoke("checkpoint", "RUN", "clean -> done @abc123")
        invoke("transition", "DONE", "clean phase completed")
        self.assertEqual(invoke("status")["clean_execution"], "COMPLETED")
        for index in range(4):
            invoke("checkpoint", "RUN", f"later checkpoint {index}")
        self.assertEqual(invoke("status")["clean_execution"], "COMPLETED")


class ReleasePolicyTests(unittest.TestCase):
    def test_push_and_ship_keep_the_versioned_release_gate(self):
        from test_guard_hostile_matrix import fresh_project

        project = fresh_project()
        before = {
            name: (project / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        for verb in ("push", "ship"):
            with self.subTest(verb=verb):
                proc = subprocess.run(
                    [sys.executable, str(TOOLS / "saipen.py"), verb, "--dry-run",
                     "--project-root", str(project), "--json"],
                    cwd=ROOT, capture_output=True, text=True, check=False,
                )
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                payload = json.loads(proc.stdout)
                self.assertEqual(payload["code"], "VALIDATION_FAILED")
                self.assertIn("VERSION is missing", payload["detail"])
        for name, expected in before.items():
            self.assertEqual((project / ".saipen" / name).read_bytes(), expected)


@unittest.skipUnless(os.name == "nt", "Windows .cmd execution is host-specific")
class WindowsLauncherTests(unittest.TestCase):
    def _launcher(self, target: Path, directory: Path) -> Path:
        cli_launcher.write_launchers(sys.executable, str(target), directory)
        return directory / "saipen.cmd"

    def test_cmd_preserves_decoded_arguments_without_shell_reinterpretation(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            probe = directory / "argv_probe.py"
            probe.write_text(
                "import json, sys\nprint(json.dumps(sys.argv[1:]))\n", encoding="utf-8"
            )
            launcher = self._launcher(probe, directory)
            proc = subprocess.run(
                [str(launcher), "ticket", "add", "P1", "value + & with spaces", "+", "status"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(
                json.loads(proc.stdout),
                ["ticket", "add", "P1", "value + & with spaces", "+", "status"],
            )
            escaped = subprocess.run(
                [str(launcher), "ticket", "add", "P1", r"\+", "+", "status"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(escaped.returncode, 0, escaped.stderr)
            self.assertEqual(
                split_cli_compound_argv(json.loads(escaped.stdout)),
                [["ticket", "add", "P1", "+"], ["status"]],
            )

    def test_cmd_reaches_canonical_dispatch_and_propagates_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            launcher = self._launcher(TOOLS / "saipen.py", Path(tmp))
            cases = (
                (["help", "+", "help"], 0, ["SEGMENT [1]: help", "SEGMENT [2]: help"]),
                (
                    ["unknown_defect_probe", "+", "help"],
                    2,
                    ["DISPOSITION [1]: FAILED", "NOT_RUN [2]: help"],
                ),
                (
                    ["help", "+", "unknown_defect_probe"],
                    2,
                    ["SEGMENT [1]: help", "DISPOSITION [2]: FAILED"],
                ),
            )
            for argv, exit_code, markers in cases:
                with self.subTest(argv=argv):
                    proc = subprocess.run(
                        [str(launcher), *argv], cwd=ROOT, capture_output=True,
                        text=True, check=False,
                    )
                    self.assertEqual(proc.returncode, exit_code, proc.stdout + proc.stderr)
                    for marker in markers:
                        self.assertIn(marker, proc.stdout)

    def test_cmd_single_arguments_and_three_segment_phase_chain(self):
        from test_guard_hostile_matrix import fresh_project

        with tempfile.TemporaryDirectory() as tmp:
            launcher = self._launcher(TOOLS / "saipen.py", Path(tmp))
            project = fresh_project()
            single = subprocess.run(
                [str(launcher), "ticket", "add", "P3", "value with spaces",
                 "--verify", "proof text", "--dry-run", "--project-root", str(project), "--json"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(single.returncode, 0, single.stdout + single.stderr)
            self.assertEqual(json.loads(single.stdout)["code"], "TICKET_ADDED")

            chain = subprocess.run(
                [str(launcher), "clean", "+", "status", "+", "validate",
                 "--project-root", str(project), "--json"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            result = json.loads(chain.stdout)
            self.assertEqual(result["code"], "COMPOUND_RESULT")
            self.assertEqual(
                [(s["command"], s["disposition"]) for s in result["segments"][:2]],
                [("clean", "SUCCEEDED"), ("status", "SUCCEEDED")],
            )
            self.assertEqual(result["segments"][0]["result"]["clean_execution"], "PENDING")
            self.assertEqual(result["segments"][1]["result"]["clean_execution"], "PENDING")
            self.assertEqual(result["segments"][2]["command"], "validate")
            self.assertEqual(chain.returncode, result["segments"][2]["exit_code"])

            clean_push_project = fresh_project()
            clean_push = subprocess.run(
                [str(launcher), "clean", "+", "push", "--project-root",
                 str(clean_push_project), "--json"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            clean_push_result = json.loads(clean_push.stdout)
            self.assertEqual(clean_push.returncode, 1, clean_push.stdout + clean_push.stderr)
            self.assertEqual(
                [(s["command"], s["disposition"]) for s in clean_push_result["segments"]],
                [("clean", "SUCCEEDED"), ("push", "FAILED")],
            )
            self.assertEqual(
                clean_push_result["segments"][0]["result"]["clean_execution"], "PENDING"
            )
            self.assertIn(
                "VERSION is missing", clean_push_result["segments"][1]["result"]["detail"]
            )

            push_project = fresh_project()
            push_build = subprocess.run(
                [str(launcher), "push", "+", "build", "ccc", "--project-root",
                 str(push_project), "--json"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            push_build_result = json.loads(push_build.stdout)
            self.assertEqual(push_build.returncode, 1, push_build.stdout + push_build.stderr)
            self.assertEqual(
                [(s["command"], s["disposition"]) for s in push_build_result["segments"]],
                [("push", "FAILED"), ("build", "NOT_RUN")],
            )


if __name__ == "__main__":
    unittest.main()
