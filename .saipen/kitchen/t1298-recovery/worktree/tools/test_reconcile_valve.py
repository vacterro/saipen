"""A tripped safety valve must never be certified CLEAN (T-1181, CORE-002).

`_state_counter_repairs` notices a valve only while the counter DISAGREES with
canonical history: at/over the cap AND ahead of the rebuild. The ordinary way a
valve trips is by honest counting -- the LOG really does hold twenty increments
and STATE really does say twenty -- and that path hits the equality `continue`,
emits no repair, and lets the whole reconciliation report CLEAN over a run
`MAINTENANCE` section 2.4 says must be paused.

Witnessed rather than imagined: `validate.py` reported the tripped valve while
`saipen continue`'s reconciliation returned CLEAN on the same STATE in the same
minute. The existing counter tests all use a disagreeing counter, which is
exactly why none of them caught it -- so the agreeing case is what is built
here.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from saipen_engine.reconcile import _tripped_valve_repairs, reconcile_protocol_state

WAIT_FORM = "WAIT: safety valve reached (0 waves / 20 tickets) -- run 'cc' to continue"


class TrippedValveInvariantTests(unittest.TestCase):
    """The pure rule, independent of any project on disk."""

    def state(self, **over):
        base = {
            "execution_intent": "goal",
            "goal_waves": 0,
            "goal_tickets": 0,
            "next_action": "PHASE BUILD T-001",
        }
        base.update(over)
        return base

    def test_under_the_caps_is_not_a_trip(self):
        self.assertEqual(_tripped_valve_repairs(self.state(goal_tickets=19, goal_waves=2)), [])

    def test_tickets_at_the_cap_refuses_even_when_counters_agree(self):
        repairs = _tripped_valve_repairs(self.state(goal_tickets=20))
        self.assertEqual(len(repairs), 1)
        self.assertEqual(repairs[0]["field"], "next_action")
        self.assertTrue(repairs[0]["refuse"])
        self.assertEqual(repairs[0]["to"], WAIT_FORM)

    def test_waves_at_the_cap_trips_independently(self):
        repairs = _tripped_valve_repairs(self.state(goal_waves=3))
        self.assertEqual(len(repairs), 1)
        self.assertIn("goal_waves=3", repairs[0]["reason"])

    def test_a_state_already_stating_the_pause_needs_no_repair(self):
        self.assertEqual(
            _tripped_valve_repairs(self.state(goal_tickets=20, next_action=WAIT_FORM)), []
        )

    def test_the_counters_are_never_tidied_by_this_rule(self):
        """They ARE the tripped condition; only `cc` clears them."""
        repairs = _tripped_valve_repairs(self.state(goal_tickets=20))
        self.assertEqual({r["field"] for r in repairs}, {"next_action"})

    def test_a_non_goal_run_owns_no_valve(self):
        self.assertEqual(
            _tripped_valve_repairs(self.state(execution_intent="normal", goal_tickets=99)), []
        )

    def test_a_malformed_counter_is_not_read_as_tripped(self):
        """A bool or a string is the counter-repair path's business, not this one."""
        self.assertEqual(_tripped_valve_repairs(self.state(goal_tickets=True)), [])
        self.assertEqual(_tripped_valve_repairs(self.state(goal_tickets="20")), [])


class ReconcileEndToEndTests(unittest.TestCase):
    """The witnessed shape, through the real entry point, on a real tree."""

    def _make_project(self, tickets: int, next_action: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix="t1181-valve-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        (root / ".saipen").mkdir(parents=True)

        # A LOG that honestly earned every increment: derived == stored, which
        # is the case the counter-repair path deliberately skips.
        lines = ["# Log", "- 30.08.26 00:00 [E-0001] [agent: tester] DEC: goal pivot -- valve"]
        for index in range(tickets):
            lines.append(
                f"- 30.08.26 00:00 [E-{index + 2:04d}] [parent: E-{index + 1:04d}] "
                f"[agent: tester] DEC: goal_tickets {index}->{index + 1}"
            )
        (root / ".saipen" / "LOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        (root / ".saipen" / "STATE.md").write_text(
            "---\n"
            "phase: SHIP\n"
            "task: T-001\n"
            f'next_action: "{next_action}"\n'
            "blocker: none\n"
            "transition_from: REVIEW\n"
            "saipen_version: 7\n"
            "schema_version: 3\n"
            f"last_event: {tickets + 1}\n"
            "style_contract: ded-4ae736e4\n"
            "agent: tester\n"
            "requires:\n  - filesystem\n  - git\n  - python\n"
            "mode: full\n"
            "updated: 2026-08-30T00:00:00Z\n"
            "execution_intent: goal\n"
            "goal_waves: 0\n"
            f"goal_tickets: {tickets}\n"
            "---\n",
            encoding="utf-8",
        )
        (root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n- [/] T-001 [P1] fix | verify: test\n## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        return root

    def test_agreeing_counters_at_the_cap_are_not_clean(self):
        root = self._make_project(20, "PHASE SHIP T-001")
        result = reconcile_protocol_state(root, "tester", dry_run=True)
        self.assertNotEqual(result["code"], "CLEAN", result)
        self.assertEqual(result["code"], "RECONCILE_REAUTH_REQUIRED", result)
        self.assertIn("next_action", result["detail"])

    def test_the_refusal_writes_nothing(self):
        root = self._make_project(20, "PHASE SHIP T-001")
        before = (root / ".saipen" / "STATE.md").read_bytes()
        reconcile_protocol_state(root, "tester", dry_run=False)
        self.assertEqual((root / ".saipen" / "STATE.md").read_bytes(), before)

    def test_a_state_already_paused_at_the_cap_is_clean(self):
        root = self._make_project(20, WAIT_FORM)
        result = reconcile_protocol_state(root, "tester", dry_run=True)
        self.assertEqual(result["code"], "CLEAN", result)

    def test_a_run_below_the_cap_is_clean(self):
        root = self._make_project(19, "PHASE SHIP T-001")
        result = reconcile_protocol_state(root, "tester", dry_run=True)
        self.assertEqual(result["code"], "CLEAN", result)


if __name__ == "__main__":
    unittest.main()
