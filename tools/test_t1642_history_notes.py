"""T-1642: sealed history is a counted fact, not a WARN.

A WARN no action can clear trains readers to skip the WARN block where the
actionable findings print. Sealed segments are immutable by append-only, so a
defect that lives only there is reported once as a `history:` PASS line, while
the same defect written into the active log keeps its WARN or FAIL.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_fixture_support import restamp_live_style  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

SCENARIO = ROOT / "tests" / "scenarios" / "userperson-valid" / ".saipen"
VALIDATOR = TOOLS / "validate.py"

DATELESS = "- [E-001] [T-none] DEC: fixture bootstrap\n"
DATED_FIRST = "- 08.08.26 00:00 [E-001] [T-none] DEC: fixture bootstrap\n"
UNTRIPPED = (
    "- 08.08.26 00:00 [E-001] [T-none] DEC: goal reauthorized -- "
    "goal_waves 0->0, goal_tickets 3->0\n"
)
SECOND = "- 08.08.26 00:01 [E-002] [parent: E-001] [T-none] DEC: fixture continues\n"


def setUpModule() -> None:
    isolate_host_session()


class HistoryNoteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1642-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        restamp_live_style(self.root / ".saipen")

    def _project(self, *, sealed: str | None, active: str, goal: bool = False) -> None:
        memory = self.root / ".saipen"
        if sealed is not None:
            (memory / "logs").mkdir()
            (memory / "logs" / "LOG-001.md").write_text(sealed, encoding="utf-8")
        (memory / "LOG.md").write_text(active, encoding="utf-8")
        last = 2 if sealed is not None or active.count("[E-") == 2 else 1
        state = (memory / "STATE.md").read_text(encoding="utf-8")
        state = state.replace("last_event: 1\n", f"last_event: {last}\n")
        if goal:
            state = state.replace(
                "mode: full\n",
                "mode: full\nexecution_intent: goal\ngoal_waves: 0\ngoal_tickets: 0\n",
            )
        (memory / "STATE.md").write_text(state, encoding="utf-8")

    def _validate(self) -> str:
        done = subprocess.run(
            [sys.executable, str(VALIDATOR), "--project-root", str(self.root), "--gate", "core"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=hermetic_env(),
            timeout=600,
        )
        return done.stdout + done.stderr

    def test_a_sealed_dateless_entry_is_history_not_a_warn(self) -> None:
        self._project(sealed=DATELESS, active=SECOND)
        out = self._validate()
        self.assertNotIn("[log-missing-date]", out)
        self.assertIn("history: 1 sealed LOG entr(y/ies) predate the mandatory DATE", out)

    def test_an_active_dateless_entry_still_fails(self) -> None:
        self._project(sealed=None, active=DATELESS)
        out = self._validate()
        self.assertIn("has no DATE", out)
        self.assertTrue(
            any(line.startswith("FAIL") and "has no DATE" in line for line in out.splitlines()),
            out,
        )

    def test_a_sealed_untripped_reauthorization_is_history(self) -> None:
        self._project(sealed=UNTRIPPED, active=SECOND, goal=True)
        out = self._validate()
        self.assertNotIn("[goal-reauth-untripped]", out)
        self.assertIn("history: 1 sealed `DEC: goal reauthorized` line(s)", out)

    def test_an_active_untripped_reauthorization_still_warns(self) -> None:
        self._project(
            sealed=DATED_FIRST,
            active=UNTRIPPED.replace("[E-001] [T-none]", "[E-002] [parent: E-001] [T-none]"),
            goal=True,
        )
        out = self._validate()
        self.assertIn("WARN [goal-reauth-untripped]", out)


if __name__ == "__main__":
    unittest.main()
