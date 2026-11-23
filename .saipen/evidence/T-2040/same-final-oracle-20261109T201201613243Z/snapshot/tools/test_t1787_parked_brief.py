"""T-1787: a routing answer keeps parked work brief.

`saipen cc --json` carried the full `_parked_work` text: 87 BLOCKED records,
28 KB of a 32 KB answer in this repository, between a model and the two
fields it must act on (`action`, `load_path`). Routing answers now keep every
parked id with its blocker class and name `saipen status --json`, which keeps
the full text.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

PROSE = "the operator must install the hook in the active profile first; " * 5
FREE = "no class prefix here, only a long free-text explanation of the wait " * 3


def setUpModule() -> None:
    isolate_host_session()


def _board() -> str:
    return (
        "## DOING\n"
        "## TODO\n"
        "- [ ] T-0001 [P1] the current work | verify: verify it\n"
        "## DONE\n"
        "## BLOCKED\n"
        "- [ ] T-0002 [P2] first parked | verify: verify it | blocker: "
        f"WAIT_USER_DECISION -- {PROSE}\n"
        f"- [ ] T-0003 [P2] second parked | verify: verify it | blocker: {FREE}\n"
    )


class ParkedBriefTests(unittest.TestCase):
    def setUp(self):
        # `goal` intent: from `normal`, `cc` first enters convergence and
        # answers CONVERGE_SET instead of a route.
        self.base, self.project = H._project(intent="goal")
        self.addCleanup(shutil.rmtree, self.base, True)
        (self.project / ".saipen" / "BOARD.md").write_text(_board(), encoding="utf-8")

    def _cli(self, *args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), *args, "--json",
             "--project-root", str(self.project)],
            cwd=str(self.project),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=hermetic_env(),
            timeout=300,
        )
        return json.loads(proc.stdout)

    def test_continue_keeps_ids_and_classes_and_names_the_detail(self):
        payload = self._cli("continue", "--dry-run")
        self.assertIn("T-0001", str(payload.get("action")), payload)
        self.assertIn("load_path", payload)
        parked = payload.get("parked_work")
        self.assertIsInstance(parked, list, payload)
        self.assertIn("T-0002 blocked: WAIT_USER_DECISION", parked)
        [free] = [entry for entry in parked if entry.startswith("T-0003 ")]
        self.assertTrue(free.endswith("..."), free)
        self.assertLessEqual(len(free), len("T-0003 blocked: ") + 80)
        self.assertEqual(payload.get("parked_detail"), "saipen status --json")

    def test_status_still_carries_the_full_text(self):
        parked = self._cli("status").get("parked_work") or []
        self.assertTrue(any(PROSE.strip() in entry for entry in parked), parked)
        self.assertTrue(any(FREE.strip() in entry for entry in parked), parked)


if __name__ == "__main__":
    unittest.main()
