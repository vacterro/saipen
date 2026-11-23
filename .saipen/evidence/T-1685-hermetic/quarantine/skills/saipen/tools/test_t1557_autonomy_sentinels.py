"""No-blocker sentinels must not let active work become a final response."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.response_surface import OperationalBoundary, render_boundary  # noqa: E402
from test_codex_stop_hook import (  # noqa: E402
    card, classify, stop_event, validation_of, wait_project,
)
from test_guard_hostile_matrix import active_project, fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def with_blocker(value: str) -> Path:
    project = active_project()
    state = project / ".saipen" / "STATE.md"
    state.write_text(
        state.read_text(encoding="utf-8").replace('blocker: ""', f'blocker: "{value}"'),
        encoding="utf-8",
    )
    return project


class ActiveSentinelRegression(unittest.TestCase):
    def test_active_sentinels_cannot_hand_back_or_invent_human_work(self):
        for sentinel in ("", "none", "NONE", "NoNe"):
            for operator in ("NONE", "Press continue so I may run the next test"):
                with self.subTest(sentinel=sentinel, operator=operator):
                    project = with_blocker(sentinel)
                    text = render_boundary(OperationalBoundary(
                        "BUILD T-9001", "Remaining work deferred", "NONE", operator,
                        "saipen continue", validation_of(project),
                    ))
                    rc, verdict = classify(project, text)
                    self.assertEqual(rc, 1, verdict)
                    self.assertEqual(verdict["turn_decision"], "AUTO_KICK", verdict)
                    self.assertEqual(verdict["class"], "AUTONOMOUS_HANDBACK", verdict)
                    _, hook, _ = stop_event(project, text)
                    self.assertEqual(hook.get("decision"), "block", hook)

    def test_active_none_does_not_turn_prose_into_ordinary_chat(self):
        project = with_blocker("none")
        text = "Work remains. Please say continue before I run the next test."
        rc, verdict = classify(project, text)
        self.assertEqual(rc, 1, verdict)
        self.assertEqual(verdict["class"], "AUTONOMOUS_HANDBACK", verdict)
        _, hook, _ = stop_event(project, text)
        self.assertEqual(hook.get("decision"), "block", hook)

    def test_real_wait_allows_the_required_human_boundary(self):
        project = wait_project()
        text = card(project, wait=True)
        rc, verdict = classify(project, text)
        self.assertEqual(rc, 0, verdict)
        self.assertEqual(verdict["class"], "VALID_BOUNDARY", verdict)
        _, hook, _ = stop_event(project, text)
        self.assertIsNone(hook)

    def test_idle_plain_chat_stays_ordinary(self):
        rc, verdict = classify(fresh_project(), "An ordinary explanation.")
        self.assertEqual(rc, 0, verdict)
        self.assertEqual(verdict["class"], "ORDINARY_CHAT", verdict)

    def test_real_blocker_does_not_autokick(self):
        project = with_blocker("HUMAN_DECISION -- choose disposition")
        _, verdict = classify(project, "A real blocker exists.")
        self.assertNotEqual(verdict["turn_decision"], "AUTO_KICK", verdict)
        self.assertNotEqual(verdict["class"], "AUTONOMOUS_HANDBACK", verdict)


if __name__ == "__main__":
    unittest.main()
