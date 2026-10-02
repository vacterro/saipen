"""T-1532: `gg "cc all"` names the CONVERGENCE CONTRACT, not new Work.

THE DEFECT THIS EXISTS FOR
`/goal cc all` is the operator asking for the `cc` contract -- CONVERGE.md
says `cc` takes the project "to a state where nothing known is left undone".
`goal_entry` planned it as if it were an objective, and `_goal_plan_steps`
emitted ONE step whose text and whose verify clause were the same sentence:

    T-1533 [P1] cc all | verify: cc all is complete and the
    repository-declared verification harness passes

That is the GOAL_ECHO class already recorded on this board as T-1306,
T-1195, T-1172 and T-1155: no evidence can ever satisfy "cc all is
complete". Worse, the pivot DEMOTED the live DOING ticket to make room for
it, so naming the contract destroyed the Work already in flight.

The fix routes a closed-vocabulary continuation directive to the operation
that already owns convergence (`set_converge_intent`), so the intent is
persisted and no ticket is invented.

CONTROLS
- `cc all` / `cc` bind converge/done, `ccc` binds converge/ship, `sc` binds
  converge/crew: the declared rows reach their declared targets.
- A live DOING ticket is NOT demoted, and no ticket is minted: the direct
  defect, measured.
- A real objective still plans normally and still demotes (T-1474 Entry
  semantics preserved) -- the fix is narrow on purpose.
- Fail-closed: an objective that merely CONTAINS a continue row is still
  planned. `cc all then also rename the module` is not a directive.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import codec  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.operations import goal_entry  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import _allocation_log, _doing, project  # noqa: E402

TICKET = "T-9100"


def setUpModule() -> None:
    isolate_host_session()


def busy(case: unittest.TestCase) -> Path:
    """A project with ONE live claimed DOING ticket: the work a pivot would destroy.

    STATE must agree with the BOARD -- a DOING ticket under a non-ticket
    phase is itself a validation failure, so the fixture carries the real
    ticket-bearing state (`phase: BUILD`, `task: T-9100`) rather than
    measuring the write gate instead of the directive.
    """
    ticket = _doing(TICKET, "live work", "test-agent", 0)
    return project(
        case,
        board=ticket,
        log=_allocation_log(TICKET),
        phase="BUILD",
        task=TICKET,
        next_action=f"PHASE BUILD {TICKET}",
        transition_from="SCOUT",
    )


def state_of(root: Path) -> dict:
    return parse_state(codec.read_doc(root / ".saipen" / "STATE.md"))


def board_of(root: Path) -> dict:
    return parse_board(codec.read_doc(root / ".saipen" / "BOARD.md"))


class ConvergeDirectiveTest(unittest.TestCase):
    """`gg <continue row> [all]` persists the declared converge intent."""

    def test_cc_all_binds_converge_done_and_invents_no_ticket(self) -> None:
        root = busy(self)
        result = goal_entry(root, "test-agent", "cc all")
        self.assertTrue(result.ok, result.message)
        self.assertEqual(result.code, "CONVERGE_SET")

        state = state_of(root)
        self.assertEqual(state.get("execution_intent"), "converge")
        self.assertEqual(state.get("converge_target"), "done")
        # The goal family owns no field here: a converge intent and a goal
        # pivot are different families and must not both be present.
        self.assertNotIn("goal_waves", state)
        self.assertNotIn("goal_tickets", state)

    def test_live_doing_ticket_is_not_demoted(self) -> None:
        """The direct defect: naming the contract used to destroy live Work."""
        root = busy(self)
        goal_entry(root, "test-agent", "cc all")
        board = board_of(root)
        doing = [t for t in board["tickets"].values() if t["section"] == "## DOING"]
        self.assertEqual([t["id"] for t in doing], [TICKET])
        # And no echo ticket was invented to take its place.
        self.assertEqual(sorted(board["tickets"]), [TICKET])
        self.assertEqual(state_of(root).get("task"), TICKET)

    def test_bare_row_and_sibling_rows_reach_their_declared_targets(self) -> None:
        for objective, target in (
            ("cc", "done"),
            ("cc all", "done"),
            ("ccc", "ship"),
            ("sc", "crew"),
        ):
            with self.subTest(objective=objective):
                root = project(self)
                result = goal_entry(root, "test-agent", objective)
                self.assertTrue(result.ok, result.message)
                state = state_of(root)
                self.assertEqual(state.get("execution_intent"), "converge")
                self.assertEqual(state.get("converge_target"), target)

    def test_objective_containing_a_row_is_still_planned(self) -> None:
        """Fail-closed: the directive is a closed vocabulary, not a substring test."""
        for objective in (
            "cc all then also rename the module",
            "cc everything must be rewritten",
            "ship the parser",
        ):
            with self.subTest(objective=objective):
                root = project(self)
                result = goal_entry(root, "test-agent", objective)
                self.assertEqual(result.code, "GOAL_SET")
                self.assertEqual(state_of(root).get("execution_intent"), "goal")

    def test_real_objective_still_plans_and_still_demotes(self) -> None:
        """T-1474 Entry semantics are untouched: a new objective pivots normally."""
        root = busy(self)
        result = goal_entry(root, "test-agent", "fix the parser")
        self.assertEqual(result.code, "GOAL_SET")
        state = state_of(root)
        self.assertEqual(state.get("execution_intent"), "goal")
        self.assertEqual(state.get("goal_waves"), 1)
        self.assertNotEqual(state.get("task"), TICKET)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
