"""T-1760 REVIEW: the verify clause on the real CLI, independent of the module.

    python review_probe.py <tools-dir>

`saipen ccc` and the validator both run as subprocesses against a fixture
project that has no Git, then against the same project after it becomes a Git
project of its own. Prints what each answered.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(sys.argv[1]).resolve()
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(TOOLS))

from test_control_primitives import ControlFixture  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

OBSERVED: dict = {}
NO_MARKER = "converge_target: ship has no ccc entry marker"


def setUpModule() -> None:
    isolate_host_session()


class RealCli(ControlFixture):
    def run_cli(self, *args: str) -> dict:
        done = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), "--project-root", str(self.project),
             "--agent", "tester", "--json", *args],
            cwd=self.project, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
        blob = (done.stdout or "") + (done.stderr or "")
        try:
            return json.loads(blob)
        except ValueError:
            return {"ok": False, "code": "UNPARSED", "detail": blob[-500:]}

    def validator(self) -> list:
        done = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "validate.py"), "--project-root", str(self.project)],
            cwd=TOOLS.parent, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=600,
        )
        out = (done.stdout or "") + (done.stderr or "")
        return [line for line in out.splitlines() if line.startswith("FAIL") and "ccc" in line]

    def test_the_route_a_no_git_project_takes(self):
        self.project = self.make_project(intent="goal", active=True)
        entered = self.run_cli("ccc")
        self.assertTrue(entered.get("ok"), entered)
        self.assertEqual(entered.get("source_head"), "no-git", entered)
        marker = [ln for ln in (self.project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
                  .splitlines() if "ccc converge target" in ln][-1]
        OBSERVED["marker the CLI wrote"] = marker.split("DEC: ", 1)[1]
        fails = self.validator()
        OBSERVED["validator ccc FAIL lines without Git"] = fails
        self.assertEqual(fails, [])
        for command in (
            ["git", "init", "-q"],
            ["git", "config", "user.email", "audit@example.invalid"],
            ["git", "config", "user.name", "Audit Fixture"],
            ["git", "config", "core.autocrlf", "false"],
            ["git", "add", "."],
            ["git", "commit", "-qm", "fixture"],
        ):
            subprocess.run(command, cwd=self.project, check=True)
        fails = self.validator()
        OBSERVED["validator ccc FAIL lines once it is a Git project"] = [f[:110] for f in fails]
        self.assertEqual(len([f for f in fails if NO_MARKER in f]), 1, fails)


if __name__ == "__main__":
    program = unittest.main(exit=False, verbosity=1)
    print(json.dumps(OBSERVED, indent=2, ensure_ascii=False))
    sys.exit(0 if program.result.wasSuccessful() else 1)
