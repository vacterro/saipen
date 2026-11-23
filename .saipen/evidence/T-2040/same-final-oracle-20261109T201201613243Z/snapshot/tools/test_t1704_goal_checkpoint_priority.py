"""T-1704: canonical budget brakes outrank audit ingestion, with counter proof.

Carrier doubles below belong only to disposable projects. The live captured
T-1703 snapshot is immutable input; no test can authorize or mutate that Work.
"""

from __future__ import annotations

import copy
import inspect
import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from saipen_engine import codec  # noqa: E402
from saipen_engine.audit_route import route_violation  # noqa: E402
from saipen_engine.log import read_history_snapshot  # noqa: E402
from saipen_engine.reconcile import _derived_goal_counters  # noqa: E402
from saipen_engine.router import goal_checkpoint_gate, route_next  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import _allocation_log, _stamp, cli, project  # noqa: E402
import test_t1494_continuation_authority as authority_fixtures  # noqa: E402

FIXTURE = json.loads(
    (TOOLS.parent / "tests/fixtures/t1703-valve-audit.json").read_text(encoding="utf-8")
)


def setUpModule():
    isolate_host_session()


def violation(current, *, counters=None, action=None):
    """Keep the same oracle executable on both pre-fix and corrected subjects."""
    kwargs = {}
    if "state" in inspect.signature(route_violation).parameters:
        kwargs.update(state=current, goal_counters=counters)
    return route_violation(
        FIXTURE["audit_projection"],
        current["next_action"] if action is None else action,
        ("T-1703",),
        **kwargs,
    )


class BrakePriorityTests(unittest.TestCase):
    def setUp(self):
        self.current = copy.deepcopy(FIXTURE["checkpoint"])
        self.counts = copy.deepcopy(FIXTURE["derived_counters"])

    def test_captured_t1703_review_valve_is_a_legal_audit_diversion(self):
        self.assertEqual((self.current["task"], self.current["phase"]), ("T-1703", "REVIEW"))
        self.assertIsNone(violation(self.current, counters=self.counts))

    def test_three_wave_valve_is_a_legal_audit_diversion(self):
        self.current.update(
            goal_waves=3,
            goal_tickets=0,
            next_action="WAIT: safety valve reached (3 waves / 0 tickets) -- run 'cc' to continue",
        )
        self.assertIsNone(violation(self.current, counters={"goal_waves": 3, "goal_tickets": 0}))

    def test_counter_overrun_is_preserved_and_still_requires_a_checkpoint(self):
        self.current.update(
            goal_tickets=21,
            next_action="WAIT: safety valve reached (0 waves / 21 tickets) -- run 'cc' to continue",
        )
        self.assertIsNone(violation(self.current, counters={"goal_waves": 0, "goal_tickets": 21}))

    def test_unproved_cap_does_not_suppress_audit(self):
        self.assertIsNotNone(violation(self.current))

    def test_fabricated_state_cap_does_not_suppress_audit(self):
        self.assertIsNotNone(
            violation(self.current, counters={"goal_waves": 0, "goal_tickets": 19})
        )

    def test_fabricated_wait_counts_do_not_suppress_audit(self):
        self.current["next_action"] = (
            "WAIT: safety valve reached (0 waves / 999 tickets) -- run 'cc' to continue"
        )
        self.assertIsNotNone(violation(self.current, counters=self.counts))

    def test_under_cap_counters_do_not_suppress_audit(self):
        self.current.update(
            goal_tickets=19,
            next_action="WAIT: safety valve reached (0 waves / 19 tickets) -- run 'cc' to continue",
        )
        self.assertIsNotNone(
            violation(self.current, counters={"goal_waves": 0, "goal_tickets": 19})
        )

    def test_wrong_intent_does_not_suppress_audit(self):
        self.current["execution_intent"] = "normal"
        self.assertIsNotNone(violation(self.current, counters=self.counts))

    def test_mismatched_state_action_does_not_suppress_audit(self):
        self.assertIsNotNone(violation(self.current, counters=self.counts, action="saipen improve"))

    def test_boolean_or_string_counter_evidence_cannot_fabricate_a_cap(self):
        for counter in (True, "20", -20):
            self.assertIsNotNone(
                violation(self.current, counters={"goal_waves": 0, "goal_tickets": counter})
            )

    def test_scope_selection_wait_remains_illegal(self):
        self.current["next_action"] = "WAIT: scope selection -- choose an audit"
        self.assertIsNotNone(violation(self.current, counters=self.counts))

    def test_user_brake_outranks_pending_ingestion(self):
        self.current["next_action"] = "WAIT: user brake -- stop here"
        self.assertIsNone(violation(self.current))

    def test_destructive_operation_gate_outranks_pending_ingestion(self):
        self.current["next_action"] = "WAIT: destructive-op -- delete the database"
        self.assertIsNone(violation(self.current))

    def test_external_state_blocker_outranks_pending_ingestion(self):
        self.current.update(
            blocker="BLOCKED_EXTERNAL: credentials unavailable", next_action="saipen status"
        )
        self.assertIsNone(violation(self.current))

    def test_blocked_phase_outranks_pending_ingestion(self):
        self.current.update(phase="BLOCKED", blocker="failed safely", next_action="saipen status")
        self.assertIsNone(violation(self.current))

    def test_a_different_wait_does_not_borrow_a_state_brake(self):
        self.current["next_action"] = "WAIT: user brake -- stop here"
        self.assertIsNotNone(
            violation(self.current, action="WAIT: scope selection -- choose an audit")
        )

    def test_live_ticket_priority_and_pending_audit_order_are_unchanged(self):
        self.assertIsNone(violation(self.current, action="PHASE REVIEW T-1703"))
        before = copy.deepcopy(FIXTURE["audit_projection"])
        violation(self.current, counters=self.counts)
        self.assertEqual(before, FIXTURE["audit_projection"])


class NativeCheckpointTests(unittest.TestCase):
    # Reuse fixture construction, never a separately maintained authority oracle.
    bounded = authority_fixtures.ContinuationAuthorityTests.bounded
    persistent = authority_fixtures.ContinuationAuthorityTests.persistent
    read_state = authority_fixtures.ContinuationAuthorityTests.read_state
    patch_state = authority_fixtures.ContinuationAuthorityTests.patch_state
    spend = authority_fixtures.ContinuationAuthorityTests.spend
    snapshot = authority_fixtures.ContinuationAuthorityTests.snapshot

    def audit(self, root):
        audit = root / "audit/1.md"
        audit.parent.mkdir(exist_ok=True)
        audit.write_text("# Independent audit\n\nFix the audit defect.\n", encoding="utf-8")

    def test_bounded_native_validator_accepts_proved_cap_with_pending_audit(self):
        root = self.bounded()
        self.audit(root)
        code, _payload, text = cli(root, "validate", "--json")
        self.assertEqual(code, 0, text)

    def test_bounded_continue_still_refuses_without_operator(self):
        root = self.bounded()
        self.audit(root)
        before = self.snapshot(root)
        code, payload, text = cli(root, "continue", "--json")
        self.assertEqual(code, 1, text)
        self.assertEqual(payload["code"], "RECONCILE_REAUTH_REQUIRED", text)
        self.assertEqual(before, self.snapshot(root))

    def test_persistent_twenty_ticket_checkpoint_continues_and_native_agrees(self):
        root = self.persistent()
        self.spend(root)
        self.audit(root)
        code, _payload, text = cli(root, "validate", "--json")
        self.assertEqual(code, 0, text)
        phase = self.read_state(root)["phase"]
        code, _payload, text = cli(root, "continue", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(self.read_state(root)["phase"], phase)
        self.assertEqual(self.read_state(root)["goal_tickets"], 0)
        self.assertTrue((root / "audit/1.md").is_file())

    def test_persistent_three_wave_checkpoint_has_the_same_priority(self):
        root = self.persistent()
        self.spend(root, tickets=0, waves=3)
        self.audit(root)
        code, _payload, text = cli(root, "validate", "--json")
        self.assertEqual(code, 0, text)
        code, _payload, text = cli(root, "continue", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(self.read_state(root)["goal_waves"], 0)

    def test_persistent_checkpoint_rejects_unearned_state_counters(self):
        root = self.persistent()
        self.patch_state(
            root,
            {
                "goal_waves": 0,
                "goal_tickets": 20,
                "next_action": FIXTURE["checkpoint"]["next_action"],
            },
        )
        routed = route_next(
            codec.read_doc(root / ".saipen/STATE.md"),
            codec.read_doc(root / ".saipen/BOARD.md"),
            current_agent="test-agent",
        )
        self.assertIsNotNone(goal_checkpoint_gate(root, routed))

    def test_counter_reconstruction_and_idempotent_checkpoint_replay(self):
        root = self.persistent()
        self.spend(root)
        code, _payload, text = cli(root, "continue", "--json")
        self.assertEqual(code, 0, text)
        code, _payload, text = cli(root, "continue", "--json")
        self.assertEqual(code, 0, text)
        log = (root / ".saipen/LOG.md").read_text(encoding="utf-8")
        self.assertEqual(log.count("DEC: goal checkpoint --"), 1)
        self.assertEqual(
            _derived_goal_counters(read_history_snapshot(root).events),
            {"goal_waves": 0, "goal_tickets": 0},
        )

    def test_review_ticket_and_phase_survive_the_bounded_native_check(self):
        lines = _allocation_log("T-1703").rstrip().splitlines()
        event = 3
        lines.append(
            f"- 10.10.26 00:00 [E-{event}] [parent: E-{event - 1}] "
            "[agent: test-agent] [op: goal-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa] "
            "DEC: goal pivot -- maintainer fixture"
        )
        for value in range(20):
            event += 1
            lines.append(
                f"- 10.10.26 00:00 [E-{event}] [parent: E-{event - 1}] "
                f"[agent: test-agent] DEC: goal_tickets {value}->{value + 1}"
            )
        board = (
            "## DOING\n- [/] T-1703 [P2] review host report | verify: report controls "
            f"| owner: test-agent | claim_time: {_stamp()}\n## TODO\n## DONE\n## BLOCKED\n"
        )
        root = project(
            self,
            board=board,
            log="\n".join(lines) + "\n",
            phase="REVIEW",
            transition_from="VERIFY",
            task="T-1703",
            execution_intent="goal",
            goal_waves=0,
            goal_tickets=20,
            next_action=FIXTURE["checkpoint"]["next_action"],
        )
        self.patch_state(root, {"saipen_home": str(TOOLS.parent)})
        self.audit(root)
        before = self.snapshot(root)
        code, _payload, text = cli(root, "validate", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(before, self.snapshot(root))
        self.assertEqual(
            (self.read_state(root)["task"], self.read_state(root)["phase"]), ("T-1703", "REVIEW")
        )


if __name__ == "__main__":
    unittest.main()
