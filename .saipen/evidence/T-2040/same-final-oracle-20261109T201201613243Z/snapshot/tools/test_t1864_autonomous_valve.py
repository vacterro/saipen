"""T-1864 (SRC-296): a tripped goal budget is a checkpoint, not an operator job.

Measured 23.10.26 on T-1865. Its VERIFY -> REVIEW transition was the twentieth
ticket, so the operation wrote `WAIT: safety valve reached (0 waves / 20
tickets) -- run 'cc' to continue` and the turn ended. Nobody was asked a
question -- there WAS no question: the grant that authorized the first ticket
authorized the twentieth, and the very next command (`cc`) cleared the same
counters without an operator anywhere in the chain. The engine knew how to
continue and stopped to ask permission for a decision it had already made.

The operator's own words are the acceptance criterion: "это должно решаться
автоматически и никогда не должно тревожить юзера... всё должно быть
автономно" -- a cap counts WORK, never authority.

What this module proves:

  * a goalled, protocol-home run that trips the cap keeps working in the SAME
    operation: counters cleared, the real route (`PHASE REVIEW T-###`)
    preserved, a `goal checkpoint` marker recorded, and no brake left behind;
  * the derived counters reconciliation reconstructs from LOG agree with the
    cleared STATE, so the checkpoint does not open a heal loop;
  * a CONSUMER project's bounded grant still writes the WAIT and still binds a
    brake -- auto-renewing it would fabricate authority the operator never
    gave (the red control that keeps this from being "always ignore the cap");
  * `goal_authority.trip_checkpoint` is the ONE owner of that decision, and it
    refuses to answer for a budget that has not tripped.

Run standalone:
    python tools/test_t1864_autonomous_valve.py
"""

from __future__ import annotations

import datetime
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
from saipen_engine.log import read_history_snapshot  # noqa: E402
from saipen_engine.reconcile import _derived_goal_counters  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

HOME_LINEAGE = "lineage-0123456789abcdef0123456789abcdef"
CONSUMER_LINEAGE = "lineage-fedcba9876543210fedcba9876543210"
TICKETS_BEFORE_TRIP = 19   # the next VERIFY -> REVIEW is ticket number 20
VALVE_WAIT = "WAIT: safety valve reached (0 waves / 20 tickets) -- run 'cc' to continue"


def setUpModule() -> None:
    isolate_host_session()


class _Project:
    """One disposable project with a counted goal history and a live VERIFY cycle."""

    def __init__(self, root: Path, lineage: str, *, tickets: int = TICKETS_BEFORE_TRIP):
        self.root = root
        (root / ".saipen").mkdir(parents=True)
        (root / ".saipen" / "IDENTITY.md").write_text(
            f"---\nproject_lineage: {lineage}\n---\n", encoding="utf-8"
        )
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines = [
            "# Log",
            "- 01.01.20 00:00 [E-001] [T-010] [agent: aleks] RUN: transition to VERIFY",
            "- 01.01.20 00:01 [E-002] [T-010] [agent: aleks] RUN: "
            "verify -> PASS [target: T-010] conf: high -- probe",
        ]
        for index in range(tickets):
            lines.append(
                f"- 01.01.20 00:02 [E-{index + 3:03d}] [agent: aleks] "
                f"DEC: goal_tickets {index}->{index + 1}"
            )
        (root / ".saipen" / "LOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (root / ".saipen" / "STATE.md").write_text(
            '---\nphase: VERIFY\ntask: T-010\nnext_action: "PHASE VERIFY T-010"\n'
            "blocker: none\ntransition_from: BUILD\nsaipen_version: 8\nagent: aleks\n"
            f"mode: full\nupdated: {now}\nexecution_intent: goal\ngoal_waves: 0\n"
            f"goal_tickets: {tickets}\n---\n",
            encoding="utf-8",
        )
        (root / ".saipen" / "BOARD.md").write_text(
            "# Board\n## DOING\n"
            "- [/] T-010 feature | owner: aleks | claim_time: 2020-01-01T00:00:00Z\n"
            "## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )

    def read(self) -> dict:
        return state.parse_state(codec.read_doc(self.root / ".saipen" / "STATE.md"))

    def log_text(self) -> str:
        return (self.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")


class _HuntProject:
    """A counted goal history at the HUNT boundary, one wave short of the cap."""

    def __init__(self, root: Path, lineage: str, *, waves: int = 2):
        self.root = root
        (root / ".saipen").mkdir(parents=True)
        (root / ".saipen" / "IDENTITY.md").write_text(
            f"---\nproject_lineage: {lineage}\n---\n", encoding="utf-8"
        )
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines = ["# Log"]
        for index in range(waves):
            lines.append(
                f"- 01.01.20 00:02 [E-{index + 1:03d}] [agent: aleks] "
                f"DEC: goal_waves {index}->{index + 1}"
            )
        (root / ".saipen" / "LOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (root / ".saipen" / "STATE.md").write_text(
            '---\nphase: HUNT\ntask: none\nnext_action: "PHASE HUNT"\n'
            "blocker: none\ntransition_from: DONE\nsaipen_version: 8\nagent: aleks\n"
            f"mode: full\nupdated: {now}\nexecution_intent: goal\ngoal_waves: {waves}\n"
            "goal_tickets: 0\n---\n",
            encoding="utf-8",
        )
        (root / ".saipen" / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
        )

    def read(self) -> dict:
        return state.parse_state(codec.read_doc(self.root / ".saipen" / "STATE.md"))

    def log_text(self) -> str:
        return (self.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")


class AutonomousValveTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.mkdtemp(prefix="saipen-t1864-")
        self.addCleanup(shutil.rmtree, td, True)
        self.tmp = Path(td)
        self.home = self.tmp / "home" / ".saipen"
        self.home.mkdir(parents=True)
        (self.home / "IDENTITY.md").write_text(
            f"---\nproject_lineage: {HOME_LINEAGE}\n---\n", encoding="utf-8"
        )
        patcher = mock.patch(
            "saipen_engine.state.running_home", return_value=self.tmp / "home"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def protocol_home_project(self, name="protocol") -> _Project:
        return _Project(self.tmp / name, HOME_LINEAGE)

    def consumer_project(self, name="consumer") -> _Project:
        return _Project(self.tmp / name, CONSUMER_LINEAGE)

    def protocol_home_hunt(self, name="hunt") -> _HuntProject:
        return _HuntProject(self.tmp / name, HOME_LINEAGE)

    # -- the fix ---------------------------------------------------------
    def test_the_tripping_transition_keeps_working_in_the_same_operation(self):
        """The twentieth ticket clears the budget instead of ending the turn."""
        project = self.protocol_home_project()
        result = operations.transition_phase(project.root, "REVIEW", "aleks")
        self.assertTrue(result.ok, result.to_dict())
        current = project.read()
        self.assertEqual((current["goal_waves"], current["goal_tickets"]), (0, 0))
        self.assertNotIn("safety valve", str(current["next_action"]))
        self.assertEqual(current["next_action"], "PHASE REVIEW T-010")
        self.assertIsNone(
            state.binding_brake(current),
            "a cleared checkpoint must not leave a brake behind",
        )
        self.assertIn("goal checkpoint -- goal_waves 0->0, goal_tickets 20->0", project.log_text())
        self.assertIn("authority_source protocol_home", project.log_text())

    def test_the_checkpoint_agrees_with_the_counters_recovery_rebuilds(self):
        """A marker whose reset disagrees with STATE opens a permanent heal loop."""
        project = self.protocol_home_project()
        self.assertTrue(operations.transition_phase(project.root, "REVIEW", "aleks").ok)
        current = project.read()
        derived = _derived_goal_counters(read_history_snapshot(project.root, lean=True).events)
        self.assertEqual(
            derived,
            {"goal_waves": current["goal_waves"], "goal_tickets": current["goal_tickets"]},
        )

    def test_the_budget_still_marks_itself_as_reached(self):
        """Autonomy must not silently delete the periodic look at the work."""
        project = self.protocol_home_project()
        self.assertTrue(operations.transition_phase(project.root, "REVIEW", "aleks").ok)
        log = project.log_text()
        self.assertIn("DEC: goal_tickets 19->20", log)
        self.assertIn("budget reached, continuing under the same grant", log)

    def test_the_resumed_route_is_the_transition_not_a_generic_continue(self):
        """A mid-flight transition knows its destination; `continue` does not."""
        project = self.protocol_home_project()
        self.assertTrue(operations.transition_phase(project.root, "REVIEW", "aleks").ok)
        self.assertEqual(project.read()["next_action"], "PHASE REVIEW T-010")

    def test_the_result_payload_reports_the_committed_counters(self):
        """T-1669's rule, at the ticket counter: the Result must not lie.

        The operation used to report `pre + 1` unconditionally. Once a tripped
        cap can commit 0, echoing the old arithmetic makes the Result disagree
        with the bytes on disk -- and a caller that trusts the payload resumes
        holding a ticket count the STATE does not have.
        """
        project = self.protocol_home_project()
        result = operations.transition_phase(project.root, "REVIEW", "aleks")
        self.assertTrue(result.ok, result.to_dict())
        committed = project.read()
        self.assertEqual(result.data.get("goal_tickets"), committed["goal_tickets"])
        self.assertEqual(result.data.get("next_action"), committed["next_action"])

    def test_the_untripped_count_still_reports_the_increment(self):
        """The same payload field, below the cap, still reports pre + 1."""
        project = _Project(self.tmp / "below-cap", HOME_LINEAGE, tickets=5)
        result = operations.transition_phase(project.root, "REVIEW", "aleks")
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.data.get("goal_tickets"), 6)
        self.assertEqual(project.read()["goal_tickets"], 6)

    def test_the_same_checkpoint_clears_the_wave_budget(self):
        """The HUNT -> ADD trip site is the symmetric half of the same fix.

        Both cap sites called `_trip_checkpoint`, but the wave branch had no
        test: a regression there would have kept the very WAIT this ticket
        removes, on the one path where a goal wave completes. Measured live
        before this test existed -- waves 2 -> 3 -> checkpoint -> 0, route
        `PHASE ADD` preserved.
        """
        project = self.protocol_home_hunt()
        result = operations.transition_phase(project.root, "ADD", "aleks")
        self.assertTrue(result.ok, result.to_dict())
        current = project.read()
        self.assertEqual((current["goal_waves"], current["goal_tickets"]), (0, 0))
        self.assertEqual(current["next_action"], "PHASE ADD")
        log = project.log_text()
        self.assertIn("DEC: goal_waves 2->3", log)
        self.assertIn("goal checkpoint -- goal_waves 3->0, goal_tickets 0->0", log)
        self.assertIn("authority_source protocol_home", log)

    # -- the control: a real operator boundary is untouched ---------------
    def test_a_consumer_bounded_grant_still_waits_for_its_operator(self):
        """THE red control: the cap is authority when the budget IS the authority."""
        project = self.consumer_project()
        result = operations.transition_phase(project.root, "REVIEW", "aleks")
        self.assertTrue(result.ok, result.to_dict())
        current = project.read()
        self.assertEqual(current["goal_tickets"], 20)
        self.assertEqual(current["next_action"], VALVE_WAIT)
        brake = state.binding_brake(current)
        self.assertIsNotNone(brake, "a bounded consumer must still bind its WAIT")
        self.assertEqual(brake[0], "wait")

    def test_the_fix_does_not_touch_the_twentieth_ticket_count_itself(self):
        """Both polarities count the work; only the response to the cap differs."""
        home_project = self.protocol_home_project("home-count")
        consumer = self.consumer_project("consumer-count")
        for project in (home_project, consumer):
            self.assertTrue(operations.transition_phase(project.root, "REVIEW", "aleks").ok)
        for project in (home_project, consumer):
            self.assertIn("DEC: goal_tickets 19->20", project.log_text())


class TripCheckpointOwnerTests(unittest.TestCase):
    """The decision has ONE owner; these pin its own contract."""

    def test_an_untripped_budget_gets_no_answer(self):
        """No cap, no decision: this must never pre-clear a budget."""
        calls = []
        with mock.patch.object(
            goal_authority, "protocol_home", side_effect=lambda _root: calls.append(1) or True
        ):
            self.assertIsNone(
                goal_authority.trip_checkpoint(
                    Path("unused"), {"execution_intent": "goal", "goal_waves": 0, "goal_tickets": 3}
                )
            )
        self.assertEqual(calls, [], "an untripped budget must not even ask who would clear it")

    def test_a_non_goal_intent_is_never_a_budget_question(self):
        self.assertIsNone(
            goal_authority.trip_checkpoint(
                Path("unused"),
                {"execution_intent": "converge", "goal_waves": 9, "goal_tickets": 99},
            )
        )

    def test_the_owner_names_the_authority_it_renews(self):
        with mock.patch.object(goal_authority, "protocol_home", return_value=True):
            decision = goal_authority.trip_checkpoint(
                Path("unused"),
                {"execution_intent": "goal", "goal_waves": 0, "goal_tickets": 20},
            )
        self.assertEqual(decision, {"source": "protocol_home"})

    # -- the persistent grant, which ALREADY promised this -----------------
    def _persistent_state(self) -> dict:
        return {
            "execution_intent": "goal",
            "goal_waves": 0,
            "goal_tickets": 20,
            "continuation_authority": "operator_persistent",
            "authority_source": "E-5",
            "authority_until": "goal_complete",
            "safety_valve_mode": "checkpoint",
            "goal_ingress": "goal-0123456789abcdef",
        }

    def test_a_proven_persistent_grant_clears_itself(self):
        """The grant already declares `safety_valve_mode: checkpoint`.

        The old trip site wrote `WAIT: safety valve ...` for this goal anyway,
        contradicting the very grant it was running under.
        """
        state = self._persistent_state()
        self.assertEqual(goal_authority.shape_errors(state), [])
        self.assertTrue(goal_authority.persistent(state))
        with mock.patch.object(goal_authority, "protocol_home", return_value=False), \
                mock.patch.object(goal_authority, "prove", return_value=[]):
            self.assertEqual(
                goal_authority.trip_checkpoint(Path("unused"), state),
                {"source": "E-5"},
            )

    def test_an_unproven_persistent_grant_still_waits(self):
        """A claim of persistence that cannot be proved is not authority."""
        state = self._persistent_state()
        with mock.patch.object(goal_authority, "protocol_home", return_value=False), \
                mock.patch.object(goal_authority, "prove", return_value=["no committed grant"]):
            self.assertIsNone(goal_authority.trip_checkpoint(Path("unused"), state))

    def test_an_unreadable_grant_journal_degrades_to_the_human_boundary(self):
        """A crash here would kill the transition that tripped the cap."""
        state = self._persistent_state()
        with mock.patch.object(goal_authority, "protocol_home", return_value=False), \
                mock.patch.object(goal_authority, "prove", side_effect=OSError("journal gone")):
            self.assertIsNone(goal_authority.trip_checkpoint(Path("unused"), state))


if __name__ == "__main__":
    unittest.main()
