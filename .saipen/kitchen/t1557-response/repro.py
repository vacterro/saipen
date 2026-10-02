"""Reproduce active-work handback through the public CLI and Codex Stop hook.

Run from the repository root. --patched exercises the candidate cold-recovery
module through an isolated launcher; canonical project files stay untouched.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRATCH = Path(__file__).resolve().parent
ROOT = SCRATCH.parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from test_hermetic_env import isolate_host_session

isolate_host_session()
tempfile.tempdir = str(SCRATCH)

from test_guard_hostile_matrix import active_project, fresh_project
from test_codex_stop_hook import card, stop_event, validation_of, wait_project
from saipen_engine.response_surface import OperationalBoundary, render_boundary

parser = argparse.ArgumentParser()
parser.add_argument("--patched", action="store_true")
OPTIONS, REMAINING = parser.parse_known_args()
ENGINE_ROOT = SCRATCH / "candidate" if OPTIONS.patched else ROOT


def check(project: Path, text: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(ENGINE_ROOT / "tools" / "saipen.py"), "response",
         "check", "--stdin", "--json", "--classify", "--auto-eligibility",
         "--project-root", str(project)],
        input=text, text=True, capture_output=True, check=False, cwd=ROOT,
    )
    return proc.returncode, json.loads(proc.stdout)


class ActiveSentinelRegression(unittest.TestCase):
    def test_active_none_sentinels_cannot_hand_back_or_invent_human_work(self):
        for sentinel in ("", "none", "NONE", "NoNe"):
            for operator in ("NONE", "Press continue so I may run the next test"):
                with self.subTest(sentinel=sentinel, operator=operator):
                    project = active_project()
                    state = project / ".saipen" / "STATE.md"
                    state.write_text(
                        state.read_text().replace('blocker: ""', f'blocker: "{sentinel}"'),
                        encoding="utf-8",
                    )
                    text = render_boundary(OperationalBoundary(
                        "BUILD T-9001", "Remaining work deferred", "NONE", operator,
                        "saipen continue", validation_of(project),
                    ))
                    rc, verdict = check(project, text)
                    self.assertEqual(rc, 1, verdict)
                    self.assertEqual(verdict["turn_decision"], "AUTO_KICK", verdict)
                    self.assertEqual(verdict["class"], "AUTONOMOUS_HANDBACK", verdict)
                    _, hook, _ = stop_event(project, text, root=ENGINE_ROOT)
                    self.assertEqual(hook.get("decision"), "block", hook)

    def test_active_none_sentinel_does_not_turn_prose_into_ordinary_chat(self):
        project = active_project()
        state = project / ".saipen" / "STATE.md"
        state.write_text(state.read_text().replace('blocker: ""', 'blocker: "none"'), encoding="utf-8")
        text = "Work remains. Please say continue before I run the next test."
        rc, verdict = check(project, text)
        self.assertEqual(rc, 1, verdict)
        self.assertEqual(verdict["class"], "AUTONOMOUS_HANDBACK", verdict)
        _, hook, _ = stop_event(project, text, root=ENGINE_ROOT)
        self.assertEqual(hook.get("decision"), "block", hook)

    def test_real_wait_allows_the_required_human_boundary(self):
        project = wait_project()
        text = card(project, wait=True)
        rc, verdict = check(project, text)
        self.assertEqual(rc, 0, verdict)
        self.assertEqual(verdict["class"], "VALID_BOUNDARY", verdict)
        _, hook, _ = stop_event(project, text, root=ENGINE_ROOT)
        self.assertIsNone(hook)

    def test_idle_plain_chat_stays_ordinary(self):
        project = fresh_project()
        rc, verdict = check(project, "An ordinary explanation.")
        self.assertEqual(rc, 0, verdict)
        self.assertEqual(verdict["class"], "ORDINARY_CHAT", verdict)

    def test_real_blocker_does_not_autokick(self):
        project = active_project()
        state = project / ".saipen" / "STATE.md"
        state.write_text(
            state.read_text().replace('blocker: ""', 'blocker: "HUMAN_DECISION -- choose disposition"'),
            encoding="utf-8",
        )
        _, verdict = check(project, "A real blocker exists.")
        self.assertNotEqual(verdict["turn_decision"], "AUTO_KICK", verdict)
        self.assertNotEqual(verdict["class"], "AUTONOMOUS_HANDBACK", verdict)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *REMAINING])
