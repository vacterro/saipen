"""T-1619 / SRC-179: controller-boundary integration tests E2E-01..E2E-10.

The 16 pure unit tests in test_t1619_goal_terminality prove the decision
PRIMITIVE returns AUTO_KICK. These tests prove the REAL boundary: the
canonical public verdict (iteration_verdict.project_iteration_verdict)
derived from temp STATE/BOARD fixtures, driven through the reference
outer-iteration controller (host_iteration.HostIterationController) and
the public CLI (saipen iteration --json).

Reference controller, not the native ZAICODE controller: the ZAICODE
repository is not available in this checkout (extensions/adapters/
registry.json zaicode stays ADVISORY), so E2E-01..E2E-10 bind the
contract the native controller must port, and the cross-repo handoff
artifact (.saipen/evidence/T-1619-zaicode-handoff.md) names the owner.
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_iteration as HI  # noqa: E402
from saipen_engine import iteration  # noqa: E402
from saipen_engine import iteration_verdict as IV  # noqa: E402

REAL_STATE = (Path(__file__).resolve().parent.parent / ".saipen" / "STATE.md").read_text(
    encoding="utf-8-sig"
)


def _seat(text, **fields):
    """Set every lifecycle field the verdict reads, present or not (T-1646).

    REAL_STATE supplies only what does not move (schema, style contract,
    home); a field left live made the verdict follow this checkout's seat --
    the family went red when the sandbox copied STATE at a tripped valve.
    """
    for key, value in fields.items():
        line = f"{key}: {value}"
        if re.search(rf"(?m)^{key}:.*$", text):
            text = re.sub(rf"(?m)^{key}:.*$", line, text)
        else:
            close = text.index("\n---", 3)
            text = text[:close] + "\n" + line + text[close:]
    return text


# SAIOPP live shape: tabular reads + todo writes, no repository execution.
SAIOPP_CAPS = {"read_tabular": True, "system_todo_write": True}
# Compatible executor: full repository execution surface.
SAIFREN_CAPS = {
    "filesystem": True,
    "git": True,
    "python": True,
    "shell": True,
    "patch": True,
}


def make_project(state_text, board_text):
    root = Path(tempfile.mkdtemp(prefix="t1619-e2e-"))
    (root / ".saipen").mkdir()
    (root / ".saipen" / "STATE.md").write_text(state_text, encoding="utf-8")
    (root / ".saipen" / "BOARD.md").write_text(board_text, encoding="utf-8")
    return root


def build_state(task="T-1618", goal_tickets=5, goal_waves=0):
    # T-1622: seat-independent. The old literal replaces assumed the live
    # checkout sat at SHIP T-1619, so any legitimate reseat (a repair ticket
    # taking the seat, goal counters moving) silently left the fixture on the
    # live task and flipped AUTO_KICK to OPERATOR_WAIT. Set the fields by
    # grammar instead, from whatever seat is live.
    # T-1682: transition_from too. Left live, a checkout at SCOUT resumed
    # from DONE made this fixture an invalid DONE -> BUILD state.
    return _seat(
        REAL_STATE,
        phase="BUILD",
        task=task,
        next_action=f'"PHASE BUILD {task}"',
        blocker="none",
        transition_from="SCOUT",
        execution_intent="goal",
        goal_tickets=goal_tickets,
        goal_waves=goal_waves,
    )


BUILD_BOARD = (
    "## DOING\n"
    "- [/] T-1618 [P1] work | verify: x | owner: test"
    " | claim_time: 2026-10-05T19:22:47Z\n"
    "## TODO\n"
    "## DONE\n"
    "## BLOCKED\n"
)

TERMINAL_BOARD = "## DOING\n## TODO\n## DONE\n## BLOCKED\n"


def terminal_state():
    # T-1622: seat-independent, same reason as build_state.
    return _seat(
        REAL_STATE,
        phase="DONE",
        task="none",
        next_action='"IDLE"',
        blocker="none",
        transition_from="SHIP",
        execution_intent="goal",
        goal_tickets=5,
        goal_waves=0,
    )


class E2E01PrematureHandback(unittest.TestCase):
    """Controller receives a provider final while BUILD work is executable."""

    def test_auto_kick_and_no_completion_ui(self):
        root = make_project(build_state(), BUILD_BOARD)
        verdict = IV.project_iteration_verdict(root)
        self.assertEqual(verdict["decision"], iteration.AUTO_KICK)
        self.assertEqual(verdict["canonical_task"], "T-1618")
        self.assertEqual(verdict["next_action"], "PHASE BUILD T-1618")
        ctrl = HI.HostIterationController(IV.required_for_state(["filesystem", "git", "python"]))
        action = ctrl.on_model_turn_finished(verdict)
        self.assertEqual(action, HI.KICK_NEXT_ITERATION)
        self.assertFalse(ctrl.goal_complete_ui_allowed(verdict))
        self.assertFalse(IV.verdict_allows_goal_complete_ui(verdict))


class E2E02TrueTerminal(unittest.TestCase):
    """Canonical goal truly terminal: UI emitted exactly once, no relaunch."""

    def test_terminal_once_then_stop(self):
        root = make_project(terminal_state(), TERMINAL_BOARD)
        verdict = IV.project_iteration_verdict(root)
        self.assertEqual(verdict["decision"], iteration.VALID_TERMINAL)
        self.assertTrue(verdict["goal_complete"])
        ctrl = HI.HostIterationController(IV.required_for_state(["filesystem", "git", "python"]))
        first = ctrl.on_model_turn_finished(verdict)
        second = ctrl.on_model_turn_finished(verdict)
        self.assertEqual(first, HI.EMIT_GOAL_COMPLETE_UI)
        self.assertEqual(second, HI.STOP_TRUTHFULLY)
        self.assertTrue(ctrl.goal_complete_ui_allowed(verdict))


class E2E03NoShellCandidate(unittest.TestCase):
    """SAIOPP-shape candidate never receives operational ownership."""

    def test_incompatible_rejected_compatible_selected(self):
        required = IV.required_for_state(["filesystem", "git", "python"])
        ctrl = HI.HostIterationController(required)
        selected, pause = ctrl.admit_candidates(
            [("saiopp", SAIOPP_CAPS), ("saifren", SAIFREN_CAPS)]
        )
        self.assertEqual(selected, "saifren")
        self.assertIsNone(pause)
        rejected = [e for e in ctrl.telemetry if e.get("event") == "candidate_rejected"]
        self.assertTrue(any(e.get("candidate") == "saiopp" for e in rejected))
        self.assertFalse(
            any(e.get("candidate") == "saiopp" and e.get("project_blocked") for e in rejected)
        )


class E2E04ModelSwitchCapabilityLoss(unittest.TestCase):
    """A switch re-admits fresh: no inheritance from the previous worker."""

    def test_each_switch_admitted_independently(self):
        required = IV.required_for_state(["filesystem", "git", "python"])
        ctrl = HI.HostIterationController(required)
        ok_good, _ = ctrl.admit_one("worker-good", SAIFREN_CAPS)
        ok_bad, missing = ctrl.admit_one("worker-bad", SAIOPP_CAPS)
        self.assertTrue(ok_good)
        self.assertFalse(ok_bad)
        self.assertTrue(len(missing) > 0)
        # Identity keys never decide: a grand model name grants nothing.
        ok_model, _ = ctrl.admit_one("x", {"model": "saiopp-ultra", "provider": "z"})
        self.assertFalse(ok_model)


class E2E05BadRouteLoop(unittest.TestCase):
    """Same incompatible candidate in one epoch: selected at most once."""

    def test_negative_epoch_does_not_reset_between_candidates(self):
        required = IV.required_for_state(["filesystem", "git", "python"])
        ctrl = HI.HostIterationController(required, epoch="cap-epoch-1")
        first, _ = ctrl.admit_candidates([("saiopp", SAIOPP_CAPS), ("saifren", SAIFREN_CAPS)])
        self.assertEqual(first, "saifren")
        # Same epoch, same list: saiopp must not become eligible again.
        second, _ = ctrl.admit_candidates([("saiopp", SAIOPP_CAPS), ("saifren", SAIFREN_CAPS)])
        self.assertEqual(second, "saifren")
        cleared = ctrl.reseat_epoch("cap-epoch-1")
        self.assertFalse(cleared)
        cleared = ctrl.reseat_epoch("cap-epoch-2")
        self.assertTrue(cleared)


class E2E06AllRoutesIncompatible(unittest.TestCase):
    """Exhaustion pauses at runtime level, Work preserved, never complete."""

    def test_pause_preserves_work(self):
        required = IV.required_for_state(["filesystem", "git", "python"])
        ctrl = HI.HostIterationController(required)
        selected, pause = ctrl.admit_candidates([("saiopp", SAIOPP_CAPS)])
        self.assertIsNone(selected)
        self.assertIsNotNone(pause)
        self.assertEqual(pause["code"], iteration.RUNTIME_PAUSED)
        self.assertFalse(pause["project_blocked"])
        self.assertFalse(pause["requires_human"])
        root = make_project(build_state(), BUILD_BOARD)
        verdict = IV.project_iteration_verdict(
            root, executor_caps=SAIOPP_CAPS, all_candidates_exhausted=True
        )
        self.assertEqual(verdict["decision"], iteration.RUNTIME_PAUSED)
        self.assertEqual(verdict["canonical_task"], "T-1618")
        self.assertFalse(IV.verdict_allows_goal_complete_ui(verdict))
        self.assertEqual(ctrl.on_model_turn_finished(verdict), HI.REPORT_RUNTIME_PAUSED)


class E2E07SafetyValve(unittest.TestCase):
    """Goal counter at the cap stops the kick without weakening the valve."""

    def test_valve_tripped_is_operator_wait(self):
        root = make_project(build_state(goal_tickets=20), BUILD_BOARD)
        verdict = IV.project_iteration_verdict(root)
        self.assertTrue(verdict["valve_tripped"])
        self.assertEqual(verdict["decision"], iteration.OPERATOR_WAIT)
        ctrl = HI.HostIterationController(IV.required_for_state(["filesystem", "git", "python"]))
        self.assertEqual(ctrl.on_model_turn_finished(verdict), HI.STOP_TRUTHFULLY)
        self.assertFalse(IV.verdict_allows_goal_complete_ui(verdict))


class E2E08RealOperatorAction(unittest.TestCase):
    """A binding brake stops truthfully through the same controller action."""

    def test_binding_brake_stops(self):
        text = re.sub(r"(?m)^blocker:.*$", "blocker: OPERATOR_WAIT fixture", build_state())
        root = make_project(text, BUILD_BOARD)
        verdict = IV.project_iteration_verdict(root)
        self.assertEqual(verdict["decision"], iteration.OPERATOR_WAIT)
        ctrl = HI.HostIterationController(IV.required_for_state(["filesystem", "git", "python"]))
        self.assertEqual(ctrl.on_model_turn_finished(verdict), HI.STOP_TRUTHFULLY)
        self.assertFalse(IV.verdict_allows_goal_complete_ui(verdict))


class E2E09PublicDecisionCommand(unittest.TestCase):
    """The host never manufactures booleans: the CLI derives the verdict."""

    def test_cli_decision_matches_library(self):
        root = make_project(build_state(), BUILD_BOARD)
        expected = IV.project_iteration_verdict(root)
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "iteration", "--json",
             "--project-root", str(root)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        for key in ("decision", "goal_complete", "canonical_task", "phase",
                    "next_action", "operator_due", "valve_tripped", "requires_human"):
            self.assertEqual(payload[key], expected[key], key)
        self.assertEqual(payload["decision"], iteration.AUTO_KICK)

    def test_cli_guard_safe_caps(self):
        root = make_project(build_state(), BUILD_BOARD)
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "iteration", "--json",
             "--cap", "shell=1", "--executor", "X", "--project-root", str(root)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertIn("decision", payload)


class E2E10UnknownDecisionVersion(unittest.TestCase):
    """Unknown/failed iteration query fails safe, never goal complete."""

    def test_unknown_verdict_pauses(self):
        ctrl = HI.HostIterationController(IV.required_for_state(["filesystem", "git", "python"]))
        self.assertEqual(ctrl.on_model_turn_finished(None), HI.REPORT_RUNTIME_PAUSED)
        self.assertEqual(ctrl.on_model_turn_finished({}), HI.REPORT_RUNTIME_PAUSED)
        future = {"schema_version": 999, "decision": iteration.VALID_TERMINAL,
                  "goal_complete": True, "state_readable": True}
        self.assertEqual(ctrl.on_model_turn_finished(future), HI.REPORT_RUNTIME_PAUSED)
        self.assertFalse(ctrl.goal_complete_ui_allowed(future))
        self.assertFalse(IV.verdict_allows_goal_complete_ui(future))
        missing = {"schema_version": 1, "decision": "SOMETHING_NEW",
                   "goal_complete": True, "state_readable": True}
        self.assertEqual(ctrl.on_model_turn_finished(missing), HI.REPORT_RUNTIME_PAUSED)
        self.assertFalse(IV.verdict_allows_goal_complete_ui(missing))


if __name__ == "__main__":
    unittest.main()
