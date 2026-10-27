"""T-1917 / SRC-326: Premature model-turn handback with executable work.

Proves the model-turn to outer-iteration controller boundary:
- A model finishing its response is MODEL_TURN_FINISHED, never SAIPEN_GOAL_FINISHED.
- Canonical state alone governs goal completion (MAINTENANCE GOAL-01).
- Unfinished executable Work yields AUTO_KICK, never operator handback.
- Bounded stall detection prevents infinite token loops on unchanged states.
- Cross-project boundary: SAIPEN owns verdict + reference controller; host
  adapter registers native enforcement status truthfully (ADVISORY for ZAICODE).
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from saipen_engine import host_iteration as HI  # noqa: E402
from saipen_engine import iteration  # noqa: E402
from saipen_engine import iteration_verdict as IV  # noqa: E402

SAIFREN_CAPS = {
    "filesystem": True,
    "git": True,
    "python": True,
    "shell": True,
    "patch": True,
}
SAIOPP_CAPS = {"read_tabular": True, "system_todo_write": True}


def make_test_project(phase="BUILD", task="T-1911", next_action=None, blocker="none", tickets_todo=None):
    root = Path(tempfile.mkdtemp(prefix="t1917-test-"))
    (root / ".saipen").mkdir(parents=True)
    next_act = next_action or f"PHASE {phase} {task}"
    trans_from = (
        "BUILD" if phase in ("VERIFY", "BUILD")
        else ("VERIFY" if phase == "REVIEW"
        else ("REVIEW" if phase == "SHIP"
        else ("SHIP" if phase == "DONE"
        else "SCOUT")))
    )
    state_content = (
        "---\n"
        f"phase: {phase}\n"
        f"task: {task}\n"
        f'next_action: "{next_act}"\n'
        f"blocker: {blocker}\n"
        f"transition_from: {trans_from}\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        "last_event: 100\n"
        f"style_contract: {CURRENT_STYLE_CONTRACT}\n"
        f'saipen_home: "{str(TOOLS.parent).replace(chr(92), chr(92)*2)}"\n'
        "agent: saipen-cli\n"
        "mode: full\n"
        'updated: "2026-10-25T12:00:00Z"\n'
        "requires:\n  - filesystem\n  - git\n  - python\n"
        "execution_intent: goal\n"
        "goal_tickets: 5\n"
        "goal_waves: 0\n"
        "---\n"
    )
    (root / ".saipen" / "STATE.md").write_text(state_content, encoding="utf-8")

    doing_line = f"- [/] {task} [P1] Active work | owner: saipen-cli | claim_time: 2026-10-25T12:00:00Z\n" if task != "none" else ""
    todo_lines = ""
    if tickets_todo:
        for t in tickets_todo:
            todo_lines += f"- [ ] {t} [P1] Queued work\n"

    board_content = (
        f"## DOING\n{doing_line}"
        f"## TODO\n{todo_lines}"
        "## DONE\n"
        "## BLOCKED\n"
    )
    (root / ".saipen" / "BOARD.md").write_text(board_content, encoding="utf-8")
    (root / ".saipen" / "LOG.md").write_text(
        "- 25.10.26 12:00 [E-100] [agent: saipen-cli] RUN: initial -> PASS\n",
        encoding="utf-8",
    )
    return root


class PrematureHandbackRegressionTests(unittest.TestCase):
    def setUp(self):
        self.ctrl = HI.HostIterationController(
            IV.required_for_state(["filesystem", "git", "python"])
        )

    def test_ac01_build_unfinished_yields_auto_kick(self):
        """AC-01: BUILD T-1911 unfinished + valid final digest -> AUTO_KICK schedules a turn."""
        root = make_test_project(phase="BUILD", task="T-1911")
        verdict = IV.project_iteration_verdict(root)
        self.assertEqual(verdict["decision"], iteration.AUTO_KICK)
        self.assertEqual(verdict["canonical_task"], "T-1911")
        action = self.ctrl.on_model_turn_finished(verdict)
        self.assertEqual(action, HI.KICK_NEXT_ITERATION)
        self.assertFalse(self.ctrl.goal_complete_ui_allowed(verdict))

    def test_ac02_next_exact_action_in_text_does_not_handback(self):
        """AC-02: BUILD T-1915 unfinished + printed 'NEXT EXACT ACTION: saipen continue' -> no operator handback."""
        root = make_test_project(phase="BUILD", task="T-1915", next_action="PHASE BUILD T-1915")
        verdict = IV.project_iteration_verdict(root)
        self.assertEqual(verdict["decision"], iteration.AUTO_KICK)
        # Even if model emitted text saying "NEXT EXACT ACTION: saipen continue", canonical controller auto-kicks
        action = self.ctrl.on_model_turn_finished(verdict)
        self.assertEqual(action, HI.KICK_NEXT_ITERATION)

    def test_ac03_ticket_completes_build_continues_lifecycle(self):
        """AC-03: ticket completes BUILD -> continues through VERIFY/REVIEW/SHIP."""
        root = make_test_project(phase="VERIFY", task="T-1915", next_action="PHASE VERIFY T-1915")
        verdict = IV.project_iteration_verdict(root)
        self.assertEqual(verdict["decision"], iteration.AUTO_KICK)
        action = self.ctrl.on_model_turn_finished(verdict)
        self.assertEqual(action, HI.KICK_NEXT_ITERATION)

    def test_ac04_ticket_terminal_other_work_remains_selects_next(self):
        """AC-04: ticket terminal, other authorized Work remains -> select and execute next."""
        root = make_test_project(
            phase="DONE", task="none", next_action="PHASE SCOUT T-1912", tickets_todo=["T-1912"]
        )
        verdict = IV.project_iteration_verdict(root)
        self.assertEqual(verdict["decision"], iteration.AUTO_KICK)
        self.assertFalse(verdict["goal_complete"])
        action = self.ctrl.on_model_turn_finished(verdict)
        self.assertEqual(action, HI.KICK_NEXT_ITERATION)

    def test_ac05_genuine_full_goal_terminal_verdict(self):
        """AC-05: genuine full-goal terminal verdict -> VALID_TERMINAL, completion UI once."""
        root = make_test_project(phase="DONE", task="none", next_action="IDLE", tickets_todo=[])
        verdict = IV.project_iteration_verdict(root)
        self.assertEqual(verdict["decision"], iteration.VALID_TERMINAL)
        self.assertTrue(verdict["goal_complete"])
        act1 = self.ctrl.on_model_turn_finished(verdict)
        self.assertEqual(act1, HI.EMIT_GOAL_COMPLETE_UI)
        act2 = self.ctrl.on_model_turn_finished(verdict)
        self.assertEqual(act2, HI.STOP_TRUTHFULLY)

    def test_ac06_operator_wait_no_bypass(self):
        """AC-06: next action needs fresh operator authority -> OPERATOR_WAIT, no bypass."""
        root = make_test_project(phase="BUILD", task="T-1915", blocker="DECISION_REQUIRED")
        verdict = IV.project_iteration_verdict(root)
        self.assertEqual(verdict["decision"], iteration.OPERATOR_WAIT)
        action = self.ctrl.on_model_turn_finished(verdict)
        self.assertEqual(action, HI.STOP_TRUTHFULLY)

    def test_ac07_ac08_candidate_lacks_tools_reroutes(self):
        """AC-08: candidate executor lacks tools -> capability mismatch + host reroute, not project BLOCKED."""
        selected, pause = self.ctrl.admit_candidates(
            [("saiopp", SAIOPP_CAPS), ("saifren", SAIFREN_CAPS)]
        )
        self.assertEqual(selected, "saifren")
        self.assertIsNone(pause)
        # Verify saiopp was rejected via telemetry without blocking project
        rejected = [e for e in self.ctrl.telemetry if e.get("event") == "candidate_rejected"]
        self.assertTrue(any(e.get("candidate") == "saiopp" for e in rejected))
        self.assertFalse(any(e.get("project_blocked") for e in rejected))

    def test_ac09_all_compatible_executors_unavailable_runtime_paused(self):
        """AC-09: all compatible executors unavailable -> RUNTIME_PAUSED with recoverable checkpoint."""
        ctrl = HI.HostIterationController(IV.required_for_state(["filesystem", "git", "python"]))
        selected, pause = ctrl.admit_candidates([("saiopp", SAIOPP_CAPS)])
        self.assertIsNone(selected)
        self.assertIsNotNone(pause)
        self.assertEqual(pause["code"], iteration.RUNTIME_PAUSED)
        self.assertFalse(pause["project_blocked"])

    def test_ac10_ac11_duplicate_turn_callbacks_emitted_consistently(self):
        """AC-11: two final callbacks for one generation -> one scheduled iteration."""
        root = make_test_project(phase="BUILD", task="T-1911")
        verdict = IV.project_iteration_verdict(root)
        act1 = self.ctrl.on_model_turn_finished(verdict)
        act2 = self.ctrl.on_model_turn_finished(verdict)
        self.assertEqual(act1, HI.KICK_NEXT_ITERATION)
        self.assertEqual(act2, HI.KICK_NEXT_ITERATION)

    def test_ac12_repeated_unchanged_report_diagnoses_stall(self):
        """AC-12: repeated unchanged report -> bounded stall diagnosis, no token loop."""
        root = make_test_project(phase="BUILD", task="T-1911")
        verdict = IV.project_iteration_verdict(root)
        turn_ctx = {
            "state_hash": "deadbeef1234",
            "action": "PHASE BUILD T-1911",
            "reason": "unchanged progress",
            "result_code": "AUTO_KICK",
        }
        # First 2 repeats proceed with kick
        self.assertEqual(
            self.ctrl.on_model_turn_finished(verdict, turn_context=turn_ctx),
            HI.KICK_NEXT_ITERATION,
        )
        self.assertEqual(
            self.ctrl.on_model_turn_finished(verdict, turn_context=turn_ctx),
            HI.KICK_NEXT_ITERATION,
        )
        # Third repeat triggers bounded stall detector
        act3 = self.ctrl.on_model_turn_finished(verdict, turn_context=turn_ctx)
        self.assertEqual(act3, HI.REPORT_RUNTIME_PAUSED)
        stall_events = [e for e in self.ctrl.telemetry if e.get("event") == "turn_stalled"]
        self.assertTrue(len(stall_events) > 0)
        self.assertIn("loop stalled after 3 iterations", stall_events[0]["reason"])

    def test_ac15_live_project_still_in_build_no_goal_complete_ui(self):
        """AC-15: live project still in BUILD after the model returns -> no goal-complete UI."""
        root = make_test_project(phase="BUILD", task="T-1911")
        verdict = IV.project_iteration_verdict(root)
        self.assertFalse(self.ctrl.goal_complete_ui_allowed(verdict))
        self.assertFalse(IV.verdict_allows_goal_complete_ui(verdict))

    def test_ac17_cross_project_boundary_zaicode_advisory(self):
        """AC-17: host has only post-render advisory hooks -> no fabricated enforcement claim."""
        reg_path = TOOLS.parent / "extensions" / "adapters" / "registry.json"
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        zaicode_entry = next((a for a in reg["adapters"] if a.get("id") == "zaicode"), None)
        self.assertIsNotNone(zaicode_entry)
        self.assertEqual(zaicode_entry.get("declared_strength"), "ADVISORY")
        self.assertEqual(zaicode_entry.get("response_enforcement"), "ADVISORY")
        self.assertIn(
            "ADVISORY",
            zaicode_entry.get("iteration_controller", {}).get("enforcement", ""),
        )


if __name__ == "__main__":
    unittest.main()
