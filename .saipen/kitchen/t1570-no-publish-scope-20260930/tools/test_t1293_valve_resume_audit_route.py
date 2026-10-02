"""T-1293: reauthorizing a tripped valve leaves a state its validator accepts.

Reproduced live (E-5784): audit/7.md was ACTIVE, `cc` reauthorized the goal
safety valve, and `tools/validate.py` went from 0 FAIL to "STATE.md audit route
not followed" -- `reauthorize_valve` wrote `next_action: saipen continue`
unconditionally, while SOURCE-AUDIT-INBOX-01 accepts only the routed audit
action or a continuation naming a DOING ticket. The reset must resume the
work that owns continuation, and must never persist a WAIT (the deadlock the
fixed value was avoiding).

The oracle is the validator's own predicate (`audit_route.route_violation`
over the real inbox projection), not a restatement of it.
"""

from __future__ import annotations

import datetime
import inspect
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

from saipen_engine import audit_inbox  # noqa: E402
from saipen_engine.audit_route import route_violation  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.operations import reauthorize_valve  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402

SCENARIO = ROOT / "tests" / "scenarios" / "userperson-valid" / ".saipen"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state(phase: str, task: str, next_action: str, transition_from: str) -> str:
    return (
        "---\n"
        f"phase: {phase}\n"
        f"task: {task}\n"
        f'next_action: "{next_action}"\n'
        "blocker: none\n"
        f"transition_from: {transition_from}\n"
        "saipen_version: 7\n"
        "schema_version: 3\n"
        "last_event: 1\n"
        'style_contract: ' + CURRENT_STYLE_CONTRACT + '\n'
        "agent: probe\n"
        "mode: full\n"
        f"updated: {_now()}\n"
        "execution_intent: goal\n"
        "goal_waves: 1\n"
        "goal_tickets: 20\n"
        "---\n"
    )


VALVE_WAIT = "WAIT: safety valve reached (1 waves / 20 tickets) -- run 'cc' to continue"


class ValveResumeFollowsTheAuditRoute(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="saipen-t1293-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        # T-1555: the fixture carries the placeholder; the copy claims THIS install.
        from test_fixture_support import restamp_live_style

        restamp_live_style(self.root / ".saipen")
        (self.root / ".saipen" / "USERPERSON.md").unlink(missing_ok=True)
        env = patch.dict(
            os.environ, {"SAIPEN_USER_CONFIG_HOME": str(Path(tmp.name) / "user-config")}
        )
        env.start()
        self.addCleanup(env.stop)

    def write(self, state: str, board: str) -> None:
        (self.root / ".saipen" / "STATE.md").write_text(state, encoding="utf-8")
        (self.root / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")

    def audit_layer(self) -> None:
        layer = self.root / "audit" / "7.md"
        layer.parent.mkdir(parents=True, exist_ok=True)
        layer.write_text("# audit\n\nfindings\n", encoding="utf-8")

    def reauthorize(self) -> str:
        grant = {}
        if "operator_authority_source" in inspect.signature(reauthorize_valve).parameters:
            # T-1494 records WHICH authority reset the valve; a fresh operator
            # grant is the case under test there, the resume value is the one here.
            grant["operator_authority_source"] = "SRC-001"
        done = reauthorize_valve(self.root, "probe", **grant)
        self.assertTrue(done.ok, done.to_dict())
        state = parse_state((self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        self.assertEqual((state["goal_waves"], state["goal_tickets"]), (0, 0))
        return str(state["next_action"])

    def violation(self, next_action: str) -> str | None:
        tickets = parse_board(
            (self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        )["tickets"]
        doing = [tid for tid, t in tickets.items() if t["section"] == "## DOING"]
        return route_violation(
            audit_inbox.projection(self.root), next_action, doing,
            ("blocked",), tickets=tickets, agent="probe",
        )

    def test_a_live_doing_ticket_resumes_by_name_under_an_active_audit(self):
        self.audit_layer()
        self.write(
            _state("REVIEW", "T-1292", VALVE_WAIT, "VERIFY"),
            "# Board\n## DOING\n"
            f"- [/] T-1292 [P1] live | verify: proof | owner: probe | claim_time: {_now()}\n"
            "## TODO\n## DONE\n## BLOCKED\n",
        )
        self.assertIsNotNone(self.violation("saipen continue"))  # the oracle can fail
        resumed = self.reauthorize()
        self.assertEqual(resumed, "PHASE REVIEW T-1292")
        self.assertIsNone(self.violation(resumed))

    def test_no_live_ticket_resumes_the_routed_audit_action(self):
        self.audit_layer()
        self.write(
            _state("DONE", "none", VALVE_WAIT, "SHIP"),
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n",
        )
        routed = audit_inbox.projection(self.root)["action"]
        self.assertIsNotNone(self.violation("saipen continue"))  # the oracle can fail
        resumed = self.reauthorize()
        self.assertEqual(resumed, routed)
        self.assertIsNone(self.violation(resumed))

    def test_without_an_audit_the_reset_still_never_persists_a_wait(self):
        self.write(
            _state("DONE", "none", VALVE_WAIT, "SHIP"),
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n",
        )
        resumed = self.reauthorize()
        self.assertEqual(resumed, "saipen continue")
        self.assertFalse(resumed.startswith("WAIT"))


if __name__ == "__main__":
    unittest.main()
