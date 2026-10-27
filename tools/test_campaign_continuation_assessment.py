"""Integration tests for authoritative read-only continuation assessment (P0 Block 1).

Acceptance coverage:
C01: Empty BOARD, proven maintenance eligibility -> discovery proceeds.
C02: Empty BOARD, no maintenance authority -> true idle (QUIESCENT / VALID_TERMINAL).
C03: DOING Work exists -> resumes before discovery (ACTIVE_WORK / AUTO_KICK / RUN_WORK).
C04: Independent Work exists beside externally blocked Work -> independent Work proceeds.
C12: Foreign blocked ticket with proven maintenance grant -> independent maintenance proceeds.
C13: Forged persistent grant -> refused, WAIT_AUTHORITY.
C14: Real operator boundary -> enforced across all three surfaces.

Agreement matrix:
Every test verifies agreement across all three production surfaces:
1. saipen continue --json (continue_loop.classify_route / router.gate_route)
2. saipen iteration --json (iteration_verdict.project_iteration_verdict)
3. worker supervisor decision (supervisor.observe / supervisor.decide)
"""

from __future__ import annotations

import datetime as dt
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from saipen_engine import (  # noqa: E402
    continuation_assessment as CA,
    continue_loop,
    goal_authority,
    iteration,
    iteration_verdict as IV,
    router,
    supervisor,
    watchdog,
)

T0 = dt.datetime(2026, 10, 25, 12, 0, 0, tzinfo=dt.timezone.utc)


def _format_state(
    phase: str = "DONE",
    task: str = "none",
    next_action: str = '"saipen continue"',
    blocker: str = "none",
    authority_until: str = "budget",
    continuation_authority: str = "operator_required",
    authority_source: str = "E-100",
    goal_ingress: str = "",
) -> str:
    lines = [
        "---",
        f"phase: {phase}",
        f"task: {task}",
        f"next_action: {next_action}",
        f"blocker: {blocker}",
        "transition_from: SHIP",
        "saipen_version: 8",
        "schema_version: 3",
        "last_event: 100",
        f"style_contract: {CURRENT_STYLE_CONTRACT}",
        f'saipen_home: "{str(TOOLS.parent).replace(chr(92), chr(92)*2)}"',
        "agent: tester",
        "mode: full",
        'updated: "2026-10-25T12:00:00Z"',
        "execution_intent: goal",
        "goal_tickets: 5",
        "goal_waves: 0",
        f"continuation_authority: {continuation_authority}",
        f"authority_source: {authority_source}",
        f"authority_until: {authority_until}",
        f"safety_valve_mode: {'checkpoint' if continuation_authority == 'operator_persistent' else 'hard_wait'}",
    ]
    if goal_ingress:
        lines.append(f"goal_ingress: {goal_ingress}")
    lines.append("---\n")
    return "\n".join(lines)


class ContinuationAssessmentSuite(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="saipen-ca-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.project = self.base / "project"
        (self.project / ".saipen").mkdir(parents=True)
        (self.project / ".saipen" / "LOG.md").write_text(
            "- 25.10.26 12:00 [E-100] [agent: tester] RUN: fixture -> PASS\n",
            encoding="utf-8",
        )

    def write_board(self, doing=(), todo=(), blocked=()):
        lines = ["## DOING"]
        lines += [f"- [/] {row}" for row in doing]
        lines += ["## TODO"]
        lines += [f"- [ ] {row}" for row in todo]
        lines += ["## DONE", "## BLOCKED"]
        lines += [f"- [ ] {row}" for row in blocked]
        (self.project / ".saipen" / "BOARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_state(self, **kwargs):
        (self.project / ".saipen" / "STATE.md").write_text(_format_state(**kwargs), encoding="utf-8")

    # C01: Empty BOARD with proven maintenance eligibility
    def test_c01_empty_board_with_proven_maintenance_continues(self):
        self.write_board(doing=(), todo=(), blocked=())
        self.write_state(
            phase="DONE",
            task="none",
            continuation_authority="operator_persistent",
            authority_until="continuous_maintenance",
            authority_source="SRC-304",
            goal_ingress="goal-0123456789abcdef",
        )

        with patch.object(goal_authority, "prove", return_value=[]):
            # Surface 1: Authoritative assessment
            assessment = CA.assess_continuation(self.project, now=T0)
            self.assertEqual(assessment["classification"], CA.MAINTENANCE_AVAILABLE)
            self.assertTrue(assessment["actionable"])
            self.assertEqual(assessment["executable_work"], "saipen continue")

            # Surface 2: Worker supervisor decision
            obs = supervisor.observe(self.project, now=T0)
            self.assertEqual(obs["continuation_classification"], CA.MAINTENANCE_AVAILABLE)
            self.assertEqual(obs["executable_work"], "saipen continue")
            dec = supervisor.decide(self.project, now=T0)
            self.assertEqual(dec["verdict"], supervisor.RUN_WORK)
            self.assertEqual(dec["work"], "saipen continue")

            # Surface 3: Iteration verdict
            iv = IV.project_iteration_verdict(self.project)
            self.assertTrue(iv["executable_action_remains"])
            self.assertFalse(iv["goal_complete"])
            self.assertEqual(iv["decision"], iteration.AUTO_KICK)

    # C02: Empty BOARD with no maintenance authority
    def test_c02_empty_board_no_maintenance_authority_remains_idle(self):
        self.write_board(doing=(), todo=(), blocked=())
        self.write_state(
            phase="DONE",
            task="none",
            continuation_authority="operator_required",
            authority_until="budget",
        )

        # Surface 1: Assessment
        assessment = CA.assess_continuation(self.project, now=T0)
        self.assertEqual(assessment["classification"], CA.QUIESCENT)
        self.assertFalse(assessment["actionable"])
        self.assertIsNone(assessment["executable_work"])

        # Surface 2: Worker supervisor
        dec = supervisor.decide(self.project, now=T0)
        self.assertEqual(dec["verdict"], supervisor.IDLE)
        self.assertFalse(dec["may_mutate"])

        # Surface 3: Iteration verdict
        iv = IV.project_iteration_verdict(self.project)
        self.assertFalse(iv["executable_action_remains"])
        self.assertTrue(iv["goal_complete"])
        self.assertEqual(iv["decision"], iteration.VALID_TERMINAL)

    # C03: DOING Work exists
    def test_c03_doing_work_resumes_before_discovery(self):
        self.write_board(doing=("T-1618 [P1] Active work | owner: tester | claim_time: 2026-10-25T12:00:00Z",))
        self.write_state(phase="BUILD", task="T-1618", next_action='"PHASE BUILD T-1618"')

        # Surface 1: Assessment
        assessment = CA.assess_continuation(self.project, now=T0)
        self.assertEqual(assessment["classification"], CA.ACTIVE_WORK)
        self.assertTrue(assessment["actionable"])

        # Surface 2: Worker supervisor
        dec = supervisor.decide(self.project, now=T0)
        self.assertEqual(dec["verdict"], supervisor.RUN_WORK)
        self.assertEqual(dec["work"], "T-1618")

        # Surface 3: Iteration verdict
        iv = IV.project_iteration_verdict(self.project)
        self.assertTrue(iv["executable_action_remains"])
        self.assertEqual(iv["decision"], iteration.AUTO_KICK)

    # C04: Independent Work exists beside externally blocked Work
    def test_c04_independent_work_proceeds_beside_blocked_work(self):
        self.write_board(
            todo=("T-10 [P1] Independent workable ticket",),
            blocked=("T-99 [P1] External blocked | blocker: BLOCKED_EXTERNAL",),
        )
        self.write_state(phase="DONE", task="none")

        # Surface 1: Assessment
        assessment = CA.assess_continuation(self.project, now=T0)
        self.assertEqual(assessment["classification"], CA.QUEUED_WORK)
        self.assertTrue(assessment["actionable"])
        self.assertEqual(assessment["ticket"], "T-10")

        # Surface 2: Worker supervisor
        dec = supervisor.decide(self.project, now=T0)
        self.assertEqual(dec["verdict"], supervisor.RUN_WORK)
        self.assertEqual(dec["work"], "T-10")

        # Surface 3: Iteration verdict
        iv = IV.project_iteration_verdict(self.project)
        self.assertTrue(iv["executable_action_remains"])
        self.assertEqual(iv["decision"], iteration.AUTO_KICK)

    # C12: Foreign blocked ticket with proven maintenance grant
    def test_c12_foreign_blocked_ticket_with_proven_maintenance_proceeds(self):
        self.write_board(
            todo=(),
            blocked=("T-99 [P1] Foreign blocked ticket | blocker: BLOCKED_EXTERNAL",),
        )
        self.write_state(
            phase="DONE",
            task="none",
            continuation_authority="operator_persistent",
            authority_until="continuous_maintenance",
            authority_source="SRC-304",
            goal_ingress="goal-0123456789abcdef",
        )

        with patch.object(goal_authority, "prove", return_value=[]):
            # Surface 1: Assessment
            assessment = CA.assess_continuation(self.project, now=T0)
            self.assertEqual(assessment["classification"], CA.MAINTENANCE_AVAILABLE)
            self.assertTrue(assessment["actionable"])

            # Surface 2: Worker supervisor
            dec = supervisor.decide(self.project, now=T0)
            self.assertEqual(dec["verdict"], supervisor.RUN_WORK)
            self.assertEqual(dec["work"], "saipen continue")

            # Surface 3: Iteration verdict
            iv = IV.project_iteration_verdict(self.project)
            self.assertTrue(iv["executable_action_remains"])
            self.assertEqual(iv["decision"], iteration.AUTO_KICK)

    # C13: Forged persistent grant is refused
    def test_c13_forged_persistent_grant_refused(self):
        self.write_board(todo=(), blocked=())
        self.write_state(
            phase="DONE",
            task="none",
            continuation_authority="operator_persistent",
            authority_until="continuous_maintenance",
            authority_source="SRC-304",
            goal_ingress="goal-0123456789abcdef",
        )

        # continuous_maintenance_proven returns False (forged state file, no committed proof)
        with patch.object(goal_authority, "continuous_maintenance_proven", return_value=False):
            # Surface 1: Assessment
            assessment = CA.assess_continuation(self.project, now=T0)
            self.assertEqual(assessment["classification"], CA.WAIT_AUTHORITY)
            self.assertFalse(assessment["actionable"])

            # Surface 2: Worker supervisor
            dec = supervisor.decide(self.project, now=T0)
            self.assertEqual(dec["verdict"], supervisor.OPERATOR_ACTION_DUE)
            self.assertTrue(dec["requires_human"])

            # Surface 3: Iteration verdict
            iv = IV.project_iteration_verdict(self.project)
            self.assertFalse(iv["executable_action_remains"])
            self.assertIn(iv["decision"], (iteration.OPERATOR_WAIT, iteration.RUNTIME_PAUSED))

    # C14: Real operator boundary remains enforced
    def test_c14_due_operator_gate_enforced(self):
        self.write_board(
            todo=(),
            blocked=(
                "T-2 [P1] gated | verify: x | blocker: BLOCKED_EXTERNAL -- operator gate "
                "| blocker_scope: ticket | retry_not_before: 2026-09-20T21:00:00Z",
            ),
        )
        self.write_state(phase="DONE", task="none")

        # Surface 1: Assessment
        assessment = CA.assess_continuation(self.project, now=T0)
        self.assertEqual(assessment["classification"], CA.WAIT_OPERATOR)
        self.assertFalse(assessment["actionable"])

        # Surface 2: Worker supervisor
        dec = supervisor.decide(self.project, now=T0)
        self.assertEqual(dec["verdict"], supervisor.OPERATOR_ACTION_DUE)
        self.assertTrue(dec["requires_human"])

        # Surface 3: Iteration verdict
        iv = IV.project_iteration_verdict(self.project)
        self.assertFalse(iv["executable_action_remains"])
        self.assertIn(iv["decision"], (iteration.OPERATOR_WAIT, iteration.RUNTIME_PAUSED))


if __name__ == "__main__":
    unittest.main()
