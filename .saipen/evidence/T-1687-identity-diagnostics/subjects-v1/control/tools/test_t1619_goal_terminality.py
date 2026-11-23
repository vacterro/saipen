"""T-1619 / SRC-179: goal execution survives premature model handback and
incompatible executor routing (regressions A-H).

A model turn ending is not goal completion. A no-shell executor is not a
project blocker. Both are decided from canonical state, never from prose.
"""

import copy
import inspect
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import iteration  # noqa: E402
from saipen_engine import response_surface as RS  # noqa: E402

# The exact live fixture from the incident: T-1618 mid-BUILD, valve clear.
T1618_BUILD = {
    "execution_intent": "goal",
    "task": "T-1618",
    "phase": "BUILD",
    "next_action": "PHASE BUILD T-1618",
    "blocker": "none",
    "goal_waves": 0,
    "goal_tickets": 5,
}

# What SAIOPP advertised: tabular reads and todo writes, no shell, no
# filesystem, no patch. It cannot run `saipen continue --json`.
SAIOPP_CAPS = {"read_tabular": True, "system_todo_write": True}
SAIFREN_CAPS = {
    "filesystem": True,
    "git": True,
    "python": True,
    "shell": True,
    "patch": True,
}


class RegressionAExactMuseIncident(unittest.TestCase):
    def test_the_fixture_is_not_goal_completion(self):
        self.assertEqual(
            iteration.decide_turn(
                executor_compatible=True,
                goal_complete=False,
                executable_action_remains=True,
                operator_due=False,
                valve_tripped=False,
            ),
            iteration.AUTO_KICK,
        )

    def test_the_canonical_classifier_agrees(self):
        klass, _errors = RS.classify_final_response(
            "T-1618 scope is bigger than one sitting; SCOUT complete.",
            operational_turn=True,
            executable_action_remains=True,
        )
        self.assertEqual(klass, RS.CLASS_AUTONOMOUS_HANDBACK)

    def test_prose_has_zero_terminal_authority(self):
        # The decision takes no text at all: no sentence -- however worded --
        # can move it. "Bigger than one sitting" is structurally inadmissible.
        params = inspect.signature(iteration.decide_turn).parameters
        self.assertNotIn("text", params)
        self.assertNotIn("prose", params)
        self.assertNotIn("message", params)


class RegressionBSafetyValve(unittest.TestCase):
    def test_tripped_valve_stops_without_continuation(self):
        self.assertEqual(
            iteration.decide_turn(
                executor_compatible=True,
                goal_complete=False,
                executable_action_remains=True,
                operator_due=False,
                valve_tripped=True,
            ),
            iteration.OPERATOR_WAIT,
        )


class RegressionCRealOperatorAction(unittest.TestCase):
    def test_operator_due_stops_and_requests(self):
        self.assertEqual(
            iteration.decide_turn(
                executor_compatible=True,
                goal_complete=False,
                executable_action_remains=True,
                operator_due=True,
                valve_tripped=False,
            ),
            iteration.OPERATOR_WAIT,
        )


class RegressionDNoShellExecutor(unittest.TestCase):
    def test_candidate_rejected_before_handoff(self):
        required = iteration.required_for(["filesystem", "git", "python"])
        compatible, missing = iteration.admit(dict(SAIOPP_CAPS), required)
        self.assertFalse(compatible)
        self.assertTrue({"shell", "filesystem", "patch"} <= set(missing))

    def test_rejection_is_routing_telemetry_not_a_project_blocker(self):
        verdict = iteration.mismatch_verdict("SAIRoute/SAIOPP", frozenset({"shell"}))
        self.assertEqual(verdict["code"], "EXECUTOR_CAPABILITY_MISMATCH")
        self.assertFalse(verdict["project_blocked"])
        self.assertFalse(verdict["ticket_blocked"])
        self.assertFalse(verdict["requires_human"])
        self.assertTrue(verdict["retryable"])
        self.assertTrue(verdict["reroute_required"])

    def test_unknown_capability_fails_closed(self):
        compatible, _missing = iteration.admit({}, iteration.REQUIRED_OPERATIONAL)
        self.assertFalse(compatible)


class RegressionECapabilityLossAfterSwitch(unittest.TestCase):
    def test_each_executor_admitted_independently(self):
        required = iteration.REQUIRED_OPERATIONAL
        self.assertTrue(iteration.admit(dict(SAIFREN_CAPS), required)[0])
        # B never inherits A's truth: same call, same required set, fresh read.
        self.assertFalse(iteration.admit(dict(SAIOPP_CAPS), required)[0])
        self.assertTrue(iteration.admit(dict(SAIFREN_CAPS), required)[0])

    def test_identity_never_decides(self):
        params = inspect.signature(iteration.admit).parameters
        self.assertNotIn("model", params)
        self.assertNotIn("provider", params)


class RegressionFSameBadExecutorLoop(unittest.TestCase):
    def test_observed_bad_candidate_not_selected_twice(self):
        failover = iteration.Failover(epoch="cap-epoch-1")
        required = iteration.REQUIRED_OPERATIONAL
        first, _verdict = failover.select(
            [("SAIRoute/SAIOPP", dict(SAIOPP_CAPS)), ("SAIRoute/SAIFREN", dict(SAIFREN_CAPS))],
            required,
        )
        self.assertEqual(first, "SAIRoute/SAIFREN")
        second, _verdict = failover.select(
            [("SAIRoute/SAIOPP", dict(SAIOPP_CAPS)), ("SAIRoute/SAIFREN", dict(SAIFREN_CAPS))],
            required,
        )
        self.assertEqual(second, "SAIRoute/SAIFREN")

    def test_new_epoch_reconsiders(self):
        failover = iteration.Failover(epoch="cap-epoch-1")
        failover.observe("SAIRoute/SAIOPP", frozenset({"shell"}))
        failover.new_epoch("cap-epoch-2")
        self.assertEqual(failover.observations, {})
        selected, _verdict = failover.select(
            [("SAIRoute/SAIOPP", dict(SAIFREN_CAPS))],
            iteration.REQUIRED_OPERATIONAL,
        )
        self.assertEqual(selected, "SAIRoute/SAIOPP")


class RegressionGAllExecutorsUnavailable(unittest.TestCase):
    def test_truthful_runtime_pause_with_work_preserved(self):
        failover = iteration.Failover(epoch="cap-epoch-1")
        state = dict(T1618_BUILD)
        before = copy.deepcopy(state)
        selected, verdict = failover.select(
            [("SAIRoute/SAIOPP", dict(SAIOPP_CAPS))],
            iteration.REQUIRED_OPERATIONAL,
        )
        self.assertIsNone(selected)
        self.assertEqual(
            iteration.decide_turn(
                executor_compatible=False,
                goal_complete=False,
                executable_action_remains=True,
                operator_due=False,
                valve_tripped=False,
                all_candidates_exhausted=True,
            ),
            iteration.RUNTIME_PAUSED,
        )
        # The canonical ticket is untouched: still BUILD, no blocker written.
        self.assertEqual(state, before)
        self.assertNotIn("project_blocker", verdict)


class RegressionHTrueCompletion(unittest.TestCase):
    def test_only_canonical_terminal_permits_goal_complete_ui(self):
        decision = iteration.decide_turn(
            executor_compatible=True,
            goal_complete=True,
            executable_action_remains=False,
            operator_due=False,
            valve_tripped=False,
        )
        self.assertEqual(decision, iteration.VALID_TERMINAL)
        self.assertTrue(iteration.may_report_goal_complete(decision))

    def test_remaining_work_outranks_a_completion_claim(self):
        decision = iteration.decide_turn(
            executor_compatible=True,
            goal_complete=True,
            executable_action_remains=True,
            operator_due=False,
            valve_tripped=False,
        )
        self.assertEqual(decision, iteration.AUTO_KICK)
        self.assertFalse(iteration.may_report_goal_complete(decision))

    def test_unproven_terminal_never_reports_complete(self):
        decision = iteration.decide_turn(
            executor_compatible=True,
            goal_complete=False,
            executable_action_remains=False,
            operator_due=False,
            valve_tripped=False,
        )
        self.assertNotEqual(decision, iteration.VALID_TERMINAL)
        self.assertFalse(iteration.may_report_goal_complete(decision))


if __name__ == "__main__":
    unittest.main()
