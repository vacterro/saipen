"""T-1785: the human surface of a dry run says it is a plan.

The CLI's human renderer printed an allow-list of keys without `dry_run`, so
`saipen checkpoint RUN ... --dry-run` answered `code: CHECKPOINTED`, exactly
what the real call answers, and a planned valve read as `VALVE_REAUTHORIZED`
(SRC-251 phase 5, the AUDAPACK report). The JSON carried `dry_run: true`; the
human surface now says the same, and nothing else about either surface moves.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

PLANNED = "dry_run: true -- planned only; nothing was written"


def setUpModule() -> None:
    isolate_host_session()


def _cli(root: Path, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "saipen.py"), "--project-root", str(root), *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


class DryRunHumanSurface(unittest.TestCase):
    def _log(self, root: Path) -> bytes:
        return (root / ".saipen" / "LOG.md").read_bytes()

    def test_a_planned_checkpoint_says_it_is_a_plan(self) -> None:
        root = fresh_project()
        before = self._log(root)
        done = _cli(root, "checkpoint", "DEC", "probe the dry run", "--dry-run")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("code: CHECKPOINTED", done.stdout)
        self.assertIn(PLANNED, done.stdout.splitlines())
        self.assertEqual(self._log(root), before)

    def test_a_planned_ticket_says_it_is_a_plan(self) -> None:
        root = fresh_project()
        before = (root / ".saipen" / "BOARD.md").read_bytes()
        done = _cli(root, "ticket", "add", "P3", "probe", "--verify", "probe", "--dry-run")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(PLANNED, done.stdout.splitlines())
        self.assertEqual((root / ".saipen" / "BOARD.md").read_bytes(), before)

    def test_the_real_call_does_not_claim_a_plan(self) -> None:
        root = fresh_project()
        before = self._log(root)
        done = _cli(root, "checkpoint", "DEC", "probe the real call")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("code: CHECKPOINTED", done.stdout)
        self.assertNotIn(PLANNED, done.stdout)
        self.assertNotEqual(self._log(root), before)

    def test_the_json_of_a_dry_run_keeps_its_shape(self) -> None:
        root = fresh_project()
        done = _cli(root, "checkpoint", "DEC", "probe the dry run", "--dry-run", "--json")
        payload = json.loads(done.stdout)
        self.assertEqual((payload.get("code"), payload.get("dry_run")), ("CHECKPOINTED", True))
        self.assertNotIn(PLANNED, done.stdout)


if __name__ == "__main__":
    unittest.main()
