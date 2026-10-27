"""T-1776 (SRC-249): the protocol home's goal valve never waits for a human.

The operator left the protocolist running overnight under a goal; at 20
tickets the bounded valve wrote its WAIT and `continue` refused with "bounded
run requires a fresh operator cc", because a Claude Code session carries no
operator carrier. The protocol's own repository is now a standing exception:
its valve is a checkpoint `cc` clears itself. A consumer project keeps the
bounded gate unchanged.
"""

from __future__ import annotations

import datetime
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import codec, goal_authority, operations, state  # noqa: E402
from saipen_engine.operator_task import ENV_TASK_FILE, ENV_TASK_SHA256  # noqa: E402

HOME_LINEAGE = "lineage-0123456789abcdef0123456789abcdef"
OTHER_LINEAGE = "lineage-fedcba9876543210fedcba9876543210"
VALVE_WAIT = "WAIT: safety valve reached (0 waves / 20 tickets) -- run 'cc' to continue"


def _identity(root: Path, lineage: str) -> None:
    (root / ".saipen").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "IDENTITY.md").write_text(
        f"---\nproject_lineage: {lineage}\n---\n", encoding="utf-8"
    )


class ProtocolHomeValveTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.mkdtemp(prefix="saipen-t1776-")
        self.addCleanup(shutil.rmtree, td, True)
        self.tmp = Path(td)
        self.home = self.tmp / "home"
        _identity(self.home, HOME_LINEAGE)
        env = {k: v for k, v in os.environ.items() if k not in (ENV_TASK_SHA256, ENV_TASK_FILE)}
        env["SAIPEN_USER_CONFIG_HOME"] = str(self.tmp / "user-config")
        for patcher in (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("saipen_engine.state.running_home", return_value=self.home),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _tripped_goal(self, name: str, lineage: str | None) -> Path:
        proj = self.tmp / name
        (proj / ".saipen").mkdir(parents=True)
        if lineage:
            _identity(proj, lineage)
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (proj / ".saipen" / "STATE.md").write_text(
            '---\nphase: BUILD\ntask: T-010\nnext_action: "PHASE BUILD T-010"\n'
            "blocker: none\ntransition_from: SCOUT\nsaipen_version: 7\nagent: aleks\n"
            f"mode: full\nupdated: {now}\nexecution_intent: goal\n"
            "goal_waves: 0\ngoal_tickets: 0\n---\n",
            encoding="utf-8",
        )
        (proj / ".saipen" / "BOARD.md").write_text(
            "# Board\n## DOING\n"
            "- [/] T-010 feature | owner: aleks | claim_time: 2020-01-01T00:00:00Z\n"
            "## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        (proj / ".saipen" / "LOG.md").write_text(
            "# Log\n\n- 01.01.20 00:00 [E-001] [T-010] [agent: aleks] RUN: build\n",
            encoding="utf-8",
        )
        result = operations.set_goal_intent(proj, "aleks", "Work the protocol overnight")
        self.assertTrue(result.ok, result.to_dict())
        path = proj / ".saipen" / "STATE.md"
        path.write_text(
            state.patch_state(
                codec.read_doc(path), {"goal_tickets": 20, "next_action": VALVE_WAIT}
            ),
            encoding="utf-8",
        )
        return proj

    def _state(self, proj: Path) -> dict:
        return state.parse_state(codec.read_doc(proj / ".saipen" / "STATE.md"))

    def test_protocol_home_is_lineage_equality_with_the_running_engine(self):
        home_copy = self.tmp / "worktree"
        _identity(home_copy, HOME_LINEAGE)
        consumer = self.tmp / "consumer"
        _identity(consumer, OTHER_LINEAGE)
        self.assertTrue(goal_authority.protocol_home(self.home))
        self.assertTrue(goal_authority.protocol_home(home_copy))
        self.assertFalse(goal_authority.protocol_home(consumer))
        self.assertFalse(goal_authority.protocol_home(self.tmp / "no-identity"))

    def test_protocol_home_cc_clears_the_valve_without_an_operator_carrier(self):
        proj = self._tripped_goal("protocol", HOME_LINEAGE)
        result = operations.reauthorize_valve(proj, "aleks")
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.code, "VALVE_REAUTHORIZED")
        current = self._state(proj)
        self.assertEqual((current["goal_waves"], current["goal_tickets"]), (0, 0))
        self.assertNotIn("safety valve", str(current["next_action"]))
        log = (proj / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn(
            "goal reauthorized -- goal_waves 0->0, goal_tickets 20->0; "
            "authority_source protocol_home",
            log,
        )

    def test_consumer_project_keeps_the_bounded_operator_gate(self):
        proj = self._tripped_goal("consumer", OTHER_LINEAGE)
        before = (proj / ".saipen" / "STATE.md").read_bytes()
        result = operations.reauthorize_valve(proj, "aleks")
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "RECONCILE_REAUTH_REQUIRED")
        self.assertIn("fresh operator cc", result.message)
        self.assertEqual((proj / ".saipen" / "STATE.md").read_bytes(), before)

    def test_status_and_iteration_report_no_operator_action_in_the_protocol_home(self):
        from saipen_engine.iteration_verdict import project_iteration_verdict

        home_proj = self._tripped_goal("protocol", HOME_LINEAGE)
        consumer = self._tripped_goal("consumer", OTHER_LINEAGE)
        self.assertEqual(
            goal_authority.describe(home_proj, self._state(home_proj))["state"], "protocol_home"
        )
        self.assertEqual(
            goal_authority.describe(consumer, self._state(consumer))["state"], "bounded"
        )
        home_verdict = project_iteration_verdict(home_proj)
        self.assertEqual(home_verdict["decision"], "AUTO_KICK", home_verdict)
        self.assertFalse(home_verdict["operator_due"])
        consumer_verdict = project_iteration_verdict(consumer)
        self.assertEqual(consumer_verdict["decision"], "OPERATOR_WAIT", consumer_verdict)

    def test_status_automation_block_continues_through_the_home_valve(self):
        from saipen_engine import automation
        from saipen_engine.board import parse_board
        from saipen_engine.router import route_next

        def block(proj: Path) -> dict:
            state_text = codec.read_doc(proj / ".saipen" / "STATE.md")
            board_text = codec.read_doc(proj / ".saipen" / "BOARD.md")
            return automation.automation_block(
                proj,
                state=state.parse_state(state_text),
                board=parse_board(board_text),
                routed=route_next(state_text, board_text),
                agent="aleks",
            )

        home = block(self._tripped_goal("protocol", HOME_LINEAGE))
        self.assertEqual(
            (home["disposition"], home["reason_code"], home["next_command"]),
            (automation.CONTINUE, "wait-safety-valve", "cc"),
            home,
        )
        self.assertFalse(home["operator_action_due"])
        consumer = block(self._tripped_goal("consumer", OTHER_LINEAGE))
        self.assertEqual(consumer["disposition"], automation.WAIT_USER, consumer)
        self.assertTrue(consumer["operator_action_due"])


if __name__ == "__main__":
    unittest.main()
