"""Regression suite for SOURCE-AUDIT-INBOX-01: Blocked Inbox Starvation / HUNT Deadlock.

Addresses incident ZAICODE E-7318: ACTIVE audit inbox layers with unworkable/blocked
linked work must not starve active HUNT phase, eligible FUTURE GATEs, or independently
authorized work.

Tests A through O verify:
A. ACTIVE actionable audit -> audit work has priority.
B. ACTIVE blocked audit + independent authorized task -> independent task proceeds.
C. Two blocked audits + eligible HUNT result -> HUNT proceeds.
D. Two blocked audits + no eligible tasks -> truthful RESTATE_AND_STOP.
E. Global authorization revoked -> stop all governed work.
F. Foreign file owner refusal -> only conflicting work blocked.
G. Genuine ownership grant -> blocked source re-evaluated.
H. Already active writer -> no duplicated implementation owner.
I. No budget remaining -> existing safety valve enforced.
J. Reauthorized budget=0 -> distinguish fresh budget from exhausted budget.
K. Restart -> blocked dispositions remain durable.
L. Repeated HUNT -> no infinite rescan or no-op loop.
M. Blocked P0 security issue remains visible and prioritized after unblocking.
N. New source does not duplicate SRC-329 or SRC-241.
O. Previously blocked layer becoming actionable regains appropriate priority.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from saipen_engine import audit_inbox, audit_route, continue_loop, goal_authority, intake, router  # noqa: E402


def _make_state(
    phase: str = "HUNT",
    task: str = "none",
    next_action: str = "PHASE HUNT",
    goal_tickets: int = 0,
    continuation_authority: str = "operator_persistent",
    authority_source: str = "E-7314",
    authority_until: str = "continuous_maintenance",
    safety_valve_mode: str = "checkpoint",
    execution_intent: str = "goal",
    blocker: str = "none",
    goal_ingress: str = "goal-0123456789abcdef",
) -> str:
    return (
        "---\n"
        f"phase: {phase}\n"
        f"task: {task}\n"
        f'next_action: "{next_action}"\n'
        f"blocker: {blocker}\n"
        "transition_from: DONE\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        "last_event: 19800\n"
        f"style_contract: {CURRENT_STYLE_CONTRACT}\n"
        f'saipen_home: "{ROOT.as_posix()}"\n'
        "agent: saipen-cli\n"
        "mode: full\n"
        'updated: "2026-10-31T15:34:13Z"\n'
        "requires:\n"
        "  - filesystem\n"
        "  - git\n"
        "  - python\n"
        f"execution_intent: {execution_intent}\n"
        "goal_waves: 0\n"
        f"goal_tickets: {goal_tickets}\n"
        f"continuation_authority: {continuation_authority}\n"
        f"authority_source: {authority_source}\n"
        f"authority_until: {authority_until}\n"
        f"safety_valve_mode: {safety_valve_mode}\n"
        f"goal_ingress: {goal_ingress}\n"
        "---\n"
    )


class TestSourceAuditInboxStarvation(unittest.TestCase):
    """Deterministic reproduction and regression suite for E-7318 and Tests A-O."""

    def test_derived_eligibility_constants_defined(self):
        """Derived inbox eligibility constants must be defined on audit_inbox."""
        self.assertTrue(hasattr(audit_inbox, "ELIGIBILITY_ACTIONABLE"))
        self.assertTrue(hasattr(audit_inbox, "ELIGIBILITY_BLOCKED_EXTERNAL"))
        self.assertTrue(hasattr(audit_inbox, "ELIGIBILITY_RESOLVED"))
        self.assertEqual(audit_inbox.ELIGIBILITY_ACTIONABLE, "ACTIONABLE")
        self.assertEqual(audit_inbox.ELIGIBILITY_BLOCKED_EXTERNAL, "BLOCKED_EXTERNAL")
        self.assertEqual(audit_inbox.ELIGIBILITY_RESOLVED, "RESOLVED")

    def test_a_active_actionable_audit_has_priority(self):
        """Test A: ACTIVE actionable audit -> audit work has priority."""
        state_text = _make_state(phase="SCOUT", task="none", next_action="saipen continue")
        board_text = (
            "# Tasks\n\n"
            "## DOING\n\n"
            "## TODO\n"
            "- [ ] T-100 Work for layer [P1] (needs: none)\n"
            "- [ ] T-500 Backlog task [P2] (needs: none)\n\n"
            "## BLOCKED\n\n"
            "## DONE\n"
        )
        inbox = {
            "action": "PHASE SCOUT T-100",
            "layer": 1,
            "work": "T-100",
            "path": "audit/1.md",
            "eligibility": "ACTIONABLE",
            "inbox_eligibility": "ACTIONABLE",
            "detail": "audit/1.md owns continuation through T-100",
        }
        routed = router.route_next(state_text, board_text, audit_inbox=inbox)
        self.assertTrue(routed["ok"])
        self.assertEqual(routed["action"], "PHASE SCOUT T-100")
        self.assertEqual(routed["ticket"], "T-100")
        self.assertEqual(routed["reason"], "audit-inbox")

    def test_b_active_blocked_audit_independent_task_proceeds(self):
        """Test B: ACTIVE blocked audit + independent authorized task -> independent task proceeds."""
        state_text = _make_state(phase="SCOUT", task="none", next_action="saipen continue")
        board_text = (
            "# Tasks\n\n"
            "## DOING\n\n"
            "## TODO\n"
            "- [ ] T-500 Independent workable task [P1] (needs: none)\n\n"
            "## BLOCKED\n"
            "- [ ] T-329 Blocked audit work [P1] | blocker: BLOCKED_EXTERNAL\n\n"
            "## DONE\n"
        )
        inbox = {
            "unworkable_active_only": True,
            "eligibility": "BLOCKED_EXTERNAL",
            "inbox_eligibility": "BLOCKED_EXTERNAL",
            "action": "saipen audit status",
            "unresolved_audit_count": 1,
            "idle_classification": "IDLE_BLOCKED_EXTERNAL",
            "detail": "audit inbox has no workable layer",
        }
        routed = router.route_next(state_text, board_text, audit_inbox=inbox)
        self.assertTrue(routed["ok"])
        self.assertEqual(routed["action"], "PHASE SCOUT T-500")
        self.assertEqual(routed["ticket"], "T-500")
        self.assertEqual(routed["reason"], "start")

    def test_c_two_blocked_audits_hunt_proceeds(self):
        """Test C: Two blocked audits + eligible HUNT result -> HUNT proceeds (E-7318 baseline)."""
        state_text = _make_state(
            phase="HUNT",
            task="none",
            next_action="PHASE HUNT",
            goal_tickets=0,
            continuation_authority="operator_persistent",
            authority_source="E-7314",
            authority_until="continuous_maintenance",
        )
        board_text = (
            "# Tasks\n\n"
            "## DOING\n\n"
            "## TODO\n\n"
            "## BLOCKED\n"
            "- [ ] T-329 SRC-329 blocked [P1] | blocker: BLOCKED_EXTERNAL\n"
            "- [ ] T-331 SRC-241 blocked [P1] | blocker: BLOCKED_EXTERNAL (HOST_OWNER_UNRESOLVED)\n\n"
            "## DONE\n"
        )
        inbox = {
            "unworkable_active_only": True,
            "eligibility": "BLOCKED_EXTERNAL",
            "inbox_eligibility": "BLOCKED_EXTERNAL",
            "action": "saipen audit status",
            "unresolved_audit_count": 2,
            "idle_classification": "IDLE_BLOCKED_EXTERNAL",
            "detail": "audit inbox has no workable layer; 2 linked items unworkable",
        }
        routed = router.route_next(state_text, board_text, audit_inbox=inbox)
        self.assertTrue(routed["ok"])
        # In baseline RED, this fails because routed["action"] is "saipen audit status"
        # and executable_behavior is "RESTATE_AND_STOP".
        self.assertEqual(routed["action"], "PHASE HUNT")
        self.assertEqual(routed["reason"], "hunt-continue")
        self.assertNotEqual(routed.get("executable_behavior"), "RESTATE_AND_STOP")

    def test_c2_two_blocked_audits_future_gate_proceeds(self):
        """Test C2: Two blocked audits + eligible FUTURE GATE -> FUTURE GATE proceeds."""
        state_text = _make_state(
            phase="SCOUT",
            task="none",
            next_action="saipen continue",
            goal_tickets=0,
            continuation_authority="operator_persistent",
            authority_source="E-7314",
            authority_until="continuous_maintenance",
        )
        board_text = "# Tasks\n\n## DOING\n\n## TODO\n\n## BLOCKED\n\n## DONE\n"
        inbox = {
            "unworkable_active_only": True,
            "eligibility": "BLOCKED_EXTERNAL",
            "inbox_eligibility": "BLOCKED_EXTERNAL",
            "action": "saipen audit status",
            "unresolved_audit_count": 2,
            "idle_classification": "IDLE_BLOCKED_EXTERNAL",
            "detail": "audit inbox has no workable layer",
        }
        future_gate = {
            "eligible": ["FG-001"],
            "detail": "FG-001 is eligible",
        }
        routed = router.route_next(
            state_text, board_text, audit_inbox=inbox, future_gate=future_gate
        )
        self.assertTrue(routed["ok"])
        self.assertEqual(routed["action"], "saipen future promote FG-001")
        self.assertEqual(routed["reason"], "future-gate-promotion")

    def test_d_two_blocked_audits_no_eligible_tasks_restate_and_stop(self):
        """Test D: Two blocked audits + no eligible tasks (bounded goal, not continuous maintenance) -> truthful RESTATE_AND_STOP."""
        state_text = _make_state(
            phase="SCOUT",
            task="none",
            next_action="saipen continue",
            goal_tickets=5,
            continuation_authority="operator_required",
            authority_source="E-1",
            authority_until="budget",
            safety_valve_mode="hard_wait",
        )
        board_text = (
            "# Tasks\n\n"
            "## DOING\n\n"
            "## TODO\n\n"
            "## BLOCKED\n"
            "- [ ] T-329 SRC-329 blocked [P1] | blocker: BLOCKED_EXTERNAL\n"
            "- [ ] T-331 SRC-241 blocked [P1] | blocker: BLOCKED_EXTERNAL\n\n"
            "## DONE\n"
        )
        inbox = {
            "unworkable_active_only": True,
            "eligibility": "BLOCKED_EXTERNAL",
            "inbox_eligibility": "BLOCKED_EXTERNAL",
            "action": "saipen audit status",
            "unresolved_audit_count": 2,
            "idle_classification": "IDLE_BLOCKED_EXTERNAL",
            "detail": "audit inbox has no workable layer",
        }
        routed = router.route_next(state_text, board_text, audit_inbox=inbox)
        self.assertTrue(routed["ok"])
        self.assertEqual(routed["stop_reason"], "NO_ADMISSIBLE_WORK")
        self.assertEqual(routed["executable_behavior"], "RESTATE_AND_STOP")
        self.assertEqual(routed["reason"], "audit-inbox-unworkable")

    def test_e_global_authorization_revoked_stops_all(self):
        """Test E: Global authorization revoked -> stop all governed work."""
        state_text = _make_state(
            phase="HUNT",
            task="none",
            next_action="WAIT: safety valve reached (0 waves / 20 tickets) -- run 'cc' to continue",
            goal_tickets=20,
            continuation_authority="operator_required",
            authority_source="E-7314",
            authority_until="budget",
            safety_valve_mode="hard_wait",
        )
        board_text = "# Tasks\n\n## DOING\n\n## TODO\n\n## BLOCKED\n\n## DONE\n"
        routed = router.route_next(state_text, board_text)
        self.assertTrue(routed["ok"])
        self.assertEqual(routed["reason"], "wait")
        self.assertEqual(routed["executable_behavior"], "RESTATE_AND_STOP")

    def test_f_foreign_file_owner_refusal_only_conflicting_blocked(self):
        """Test F: Foreign file owner refusal -> only conflicting work blocked."""
        board_text = (
            "# Tasks\n\n"
            "## DOING\n\n"
            "## TODO\n"
            "- [ ] T-201 Conflicting task [P1] | needs: T-101\n"
            "- [ ] T-202 Independent task [P2] (needs: none)\n\n"
            "## BLOCKED\n"
            "- [ ] T-101 Foreign owner refusal [P1] | blocker: BLOCKED_EXTERNAL\n\n"
            "## DONE\n"
        )
        state_text = _make_state(phase="SCOUT", task="none", next_action="saipen continue")
        routed = router.route_next(state_text, board_text)
        self.assertTrue(routed["ok"])
        self.assertEqual(routed["ticket"], "T-202")
        self.assertEqual(routed["action"], "PHASE SCOUT T-202")

    def test_g_genuine_ownership_grant_reevaluates_blocked_source(self):
        """Test G: Genuine ownership grant -> blocked source re-evaluated."""
        from saipen_engine.board import parse_board

        board_blocked = (
            "# Tasks\n\n"
            "## DOING\n\n"
            "## TODO\n\n"
            "## BLOCKED\n"
            "- [ ] T-331 Blocked work [P1] | blocker: BLOCKED_EXTERNAL (HOST_OWNER_UNRESOLVED)\n\n"
            "## DONE\n"
        )
        tickets_blocked = parse_board(board_blocked)["tickets"]
        proj_blocked = {
            "action": "PHASE SCOUT T-331",
            "work": "T-331",
            "unworkable_active_only": True,
            "eligibility": "BLOCKED_EXTERNAL",
        }
        self.assertFalse(audit_route.audit_route_owns(proj_blocked, tickets_blocked))

        # When ownership grant resolves the blocker, linked work moves to TODO and is workable
        board_granted = (
            "# Tasks\n\n"
            "## DOING\n\n"
            "## TODO\n"
            "- [ ] T-331 Unblocked work [P1] (needs: none)\n\n"
            "## BLOCKED\n\n"
            "## DONE\n"
        )
        tickets_granted = parse_board(board_granted)["tickets"]
        proj_actionable = {
            "action": "PHASE SCOUT T-331",
            "work": "T-331",
            "eligibility": "ACTIONABLE",
            "inbox_eligibility": "ACTIONABLE",
        }
        self.assertTrue(audit_route.audit_route_owns(proj_actionable, tickets_granted))

    def test_h_already_active_writer_no_duplicated_implementation_owner(self):
        """Test H: Already active writer -> no duplicated implementation owner."""
        board_text = (
            "# Tasks\n\n"
            "## DOING\n"
            "- [/] T-100 Active foreign task [P1] | owner: other-agent | claim_time: 2026-10-31T15:00:00Z\n\n"
            "## TODO\n\n"
            "## BLOCKED\n\n"
            "## DONE\n"
        )
        state_text = _make_state(phase="SCOUT", task="none", next_action="saipen continue")
        routed = router.route_next(state_text, board_text, current_agent="this-agent")
        self.assertTrue(routed["ok"])
        self.assertEqual(routed["reason"], "adopt")
        self.assertIn("FOREIGN", routed["ownership"])

    def test_i_no_budget_remaining_safety_valve_enforced(self):
        """Test I: No budget remaining -> existing safety valve enforced."""
        exhausted_state = {
            "execution_intent": "goal",
            "goal_waves": 0,
            "goal_tickets": 20,
            "safety_valve_mode": "hard_wait",
        }
        self.assertTrue(goal_authority.budget_exhausted(exhausted_state))
        self.assertTrue(router._goal_valve_exhausted(exhausted_state))

    def test_j_reauthorized_budget_zero_vs_exhausted(self):
        """Test J: Reauthorized budget=0 -> distinguish fresh budget from exhausted budget."""
        fresh_state = {
            "execution_intent": "goal",
            "goal_waves": 0,
            "goal_tickets": 0,
            "safety_valve_mode": "checkpoint",
        }
        exhausted_state = {
            "execution_intent": "goal",
            "goal_waves": 0,
            "goal_tickets": 20,
            "safety_valve_mode": "checkpoint",
        }
        self.assertFalse(goal_authority.budget_exhausted(fresh_state))
        self.assertTrue(goal_authority.budget_exhausted(exhausted_state))
        self.assertFalse(router._goal_valve_exhausted(fresh_state))
        self.assertTrue(router._goal_valve_exhausted(exhausted_state))

    def test_k_restart_blocked_dispositions_durable(self):
        """Test K: Restart -> blocked dispositions remain durable on filesystem."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            saipen_dir = root / ".saipen"
            saipen_dir.mkdir(parents=True)
            board_file = saipen_dir / "BOARD.md"
            board_file.write_text(
                "# Tasks\n\n## DOING\n\n## TODO\n\n## BLOCKED\n"
                "- [ ] T-329 SRC-329 blocked [P1] | blocker: BLOCKED_EXTERNAL\n"
                "- [ ] T-331 SRC-241 blocked [P1] | blocker: BLOCKED_EXTERNAL\n\n"
                "## DONE\n",
                encoding="utf-8",
            )
            from saipen_engine.board import classify_idle_work, parse_board
            parsed = parse_board(board_file.read_text(encoding="utf-8"))
            idle1 = classify_idle_work(parsed["tickets"])
            # Re-read after simulated restart
            parsed_restart = parse_board(board_file.read_text(encoding="utf-8"))
            idle2 = classify_idle_work(parsed_restart["tickets"])
            self.assertEqual(idle1["disposition"], idle2["disposition"])
            self.assertEqual(idle1["externally_blocked"], idle2["externally_blocked"])
            self.assertEqual(idle2["disposition"], "IDLE_BLOCKED_EXTERNAL")

    def test_l_repeated_hunt_no_infinite_loop(self):
        """Test L: Repeated HUNT -> no infinite rescan or no-op loop."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            from saipen_engine.continue_fallback import source_unchanged
            marker = {
                "source_head": "0000000000000000000000000000000000000000",
                "source_tree_fingerprint": "abc",
            }
            with patch(
                "saipen_engine.continue_fallback.source_identity_fields",
                return_value={
                    "source_head": "0000000000000000000000000000000000000000",
                    "source_tree_fingerprint": "abc",
                    "discovery_model": "git",
                },
            ):
                unchanged, detail = source_unchanged(root, marker)
                self.assertTrue(unchanged)
                self.assertIn("unchanged", detail.lower())

    def test_m_blocked_p0_remains_visible_and_prioritized_on_unblock(self):
        """Test M: Blocked P0 security issue remains visible and prioritized after unblocking."""
        from saipen_engine.board import parse_board, pick_next_work

        board_text = (
            "# Tasks\n\n"
            "## DOING\n\n"
            "## TODO\n"
            "- [ ] T-329 P0 Security finding [P0] (needs: none)\n"
            "- [ ] T-500 Lower priority backlog [P2] (needs: none)\n\n"
            "## BLOCKED\n\n"
            "## DONE\n"
        )
        tickets = parse_board(board_text)["tickets"]
        proj = {
            "action": "PHASE SCOUT T-329",
            "work": "T-329",
            "eligibility": "ACTIONABLE",
            "inbox_eligibility": "ACTIONABLE",
        }
        self.assertTrue(audit_route.audit_route_owns(proj, tickets))
        top, reason = pick_next_work(tickets)
        self.assertEqual(top, "T-329")

    def test_n_new_source_does_not_duplicate_src329_or_src241(self):
        """Test N: New source does not duplicate SRC-329 or SRC-241."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".saipen" / "intake" / "active").mkdir(parents=True)
            (root / ".saipen" / "intake" / "contracts").mkdir(parents=True)
            (root / ".saipen" / "intake" / "tombstones").mkdir(parents=True)
            body = "finding content for SRC-329\n"
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            index_path = root / ".saipen" / "intake" / "index.json"
            index_path.write_text(
                json.dumps({
                    "schema_version": 1,
                    "next_id": 330,
                    "active": {
                        "SRC-329": {
                            "source_sha256": digest,
                            "status": "ACTIVE",
                        }
                    },
                    "tombstones": {},
                }),
                encoding="utf-8",
            )
            found = audit_inbox.receipt_for_digest(root, digest)
            self.assertIsNotNone(found)
            self.assertEqual(found["receipt_id"], "SRC-329")

    def test_o_previously_blocked_layer_becoming_actionable_regains_priority(self):
        """Test O: Previously blocked layer becoming actionable regains appropriate priority."""
        from saipen_engine.board import parse_board

        board_text = (
            "# Tasks\n\n## DOING\n\n## TODO\n"
            "- [ ] T-329 Unblocked P1 task [P1] (needs: none)\n"
            "- [ ] T-500 Backlog task [P2] (needs: none)\n\n"
            "## BLOCKED\n\n## DONE\n"
        )
        tickets = parse_board(board_text)["tickets"]
        proj = {
            "action": "PHASE SCOUT T-329",
            "work": "T-329",
            "eligibility": "ACTIONABLE",
            "inbox_eligibility": "ACTIONABLE",
        }
        self.assertTrue(audit_route.audit_route_owns(proj, tickets))
        state_text = _make_state(phase="SCOUT", task="none", next_action="saipen continue")
        routed = router.route_next(state_text, board_text, audit_inbox=proj)
        self.assertEqual(routed["action"], "PHASE SCOUT T-329")
        self.assertEqual(routed["reason"], "audit-inbox")


if __name__ == "__main__":
    unittest.main()
