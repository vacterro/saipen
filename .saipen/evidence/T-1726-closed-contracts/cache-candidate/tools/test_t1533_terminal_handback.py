"""A continuation reservation releases when its HOLDER goes terminal (T-1533).

THE DEADLOCK THIS EXISTS FOR
T-1473 made `ticket unblock` return the seat to Work parked on the seat's
ACTIVE ticket. Its precondition required that holder to be exactly that:
`## DOING`, `state.task == holder`, a ticket-bearing phase, and claimed by
this actor. A holder that instead reached a TERMINAL section can never again
satisfy any of those, so the parked Work became permanently unreachable --
measured on T-1528, whose holder T-1532 went `## BLOCKED`:

    ticket unblock T-1528  -> CONTINUATION_RESERVED
    claim T-1528           -> TICKET_NOT_WORKABLE (carries a blocker)
    ticket block T-1528    -> ILLEGAL_TICKET_LIFECYCLE (block takes DOING/TODO)

No canonical command could lift it, and the reconcile stale-blocker repair
runs the OTHER way: it strips `blocked_on` only when the section is NOT
`## BLOCKED` (reconcile.py), so it never rescues a parked ticket either. That
is the SRC-039 class -- a correctly detected brake with no lawful action that
can release it -- and it strands real board Work.

THE FIX
A terminal holder (`## DONE` or `## BLOCKED`) is a RELEASE condition rather
than a refusal. The live-DOING arm is unchanged, so the mid-flight handback
T-1473 shipped still behaves exactly as before, and the actor still only ever
hands over the seat it holds.

CONTROLS
  RED 1  holder ## BLOCKED -> parked Work restored to DOING at its saved phase,
         holder left in ## BLOCKED (NOT resurrected into TODO), LOG honest
         about a terminal handback;
  RED 2  holder ## DONE    -> same release, holder left DONE;
  RED 3  live DOING holder -> the T-1473 arm still demotes it to TODO
         (regression guard on the pre-existing behavior);
  RED 4  live DOING holder owned by ANOTHER seat -> live-seat guard refuses with
         TICKET_NOT_WORKABLE, zero writes (the actor never hands over a seat it does not hold);
  RED 5  parked Work with its own unmet dependency -> still TICKET_NOT_WORKABLE,
         zero writes (the release is not a dependency bypass).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.fast_check import validate_texts  # noqa: E402
from saipen_engine.operations import (  # noqa: E402
    apply_claim,
    finish_ticket,
    ticket_move,
)
from test_dependency_resume_liveness import AGENT, OTHER  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1473_handback import HandbackFixture  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def board_text(project: Path) -> str:
    return (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")


def tickets(project: Path) -> dict:
    return parse_board(board_text(project))["tickets"]


def clean(project: Path) -> list[str]:
    return validate_texts(
        (project / ".saipen" / "STATE.md").read_text(encoding="utf-8"),
        board_text(project),
        (project / ".saipen" / "LOG.md").read_text(encoding="utf-8"),
        current_agent=AGENT,
    )


class TerminalHolderHandback(HandbackFixture):
    """Park a ticket, then drive its holder terminal and release the seat."""

    def terminal_holder(self, project: Path, section: str) -> tuple[str, str]:
        parked, request = self.paused(project)
        self.assertTrue(apply_claim(project, request, AGENT).ok)
        if section == "## BLOCKED":
            blocked = ticket_move(
                project,
                "block",
                request,
                AGENT,
                "holder cannot proceed; parked Work must still be reachable",
            )
            self.assertTrue(blocked.ok, blocked.to_dict())
            self.assertEqual(tickets(project)[request]["section"], "## BLOCKED")
        else:  # ## DONE -- close the holder through its own lifecycle
            self.to_ship(project, request)
            done = finish_ticket(project, request, AGENT)
            self.assertTrue(done.ok, done.to_dict())
            self.assertEqual(tickets(project)[request]["section"], "## DONE")
        return parked, request

    def release(self, project: Path, parked: str, request: str):
        return ticket_move(
            project, "unblock", parked, AGENT, f"{request} is terminal; the seat returns"
        )


class TerminalHolderReleaseTests(TerminalHolderHandback):
    def test_red1_blocked_holder_releases_the_seat(self) -> None:
        project = self.make_project()
        parked, request = self.terminal_holder(project, "## BLOCKED")
        holder_before = {
            key: value
            for key, value in tickets(project)[request].items()
            if key != "line_no"
        }

        result = self.release(project, parked, request)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.code, "HANDBACK")

        restored = tickets(project)[parked]
        self.assertEqual(restored["section"], "## DOING")
        self.assertEqual(restored["fields"].get("owner"), AGENT)
        for field in ("blocker", "blocker_scope", "blocked_on", "resume_phase",
                      "resume_transition_from"):
            self.assertNotIn(field, restored["fields"], restored["fields"])

        # The terminal holder is NOT resurrected into TODO: it is still blocked
        # for its own reason, and the release must not fake progress on it.
        self.assertEqual(tickets(project)[request]["section"], "## BLOCKED")
        holder_after = {
            key: value
            for key, value in tickets(project)[request].items()
            if key != "line_no"
        }
        self.assertEqual(holder_after, holder_before)

        state = self.state(project)
        self.assertEqual(state["phase"], "VERIFY")
        self.assertEqual(state["task"], parked)
        self.assertEqual(state["next_action"], f"PHASE VERIFY {parked}")

        log = self.log_text(project).splitlines()
        self.assertTrue(any("terminal" in line and f"[{request}]" in line for line in log), log)
        self.assertFalse(
            any("checkpointed to TODO" in line and f"[{request}]" in line for line in log),
            "a terminal holder must not be logged as demoted to TODO",
        )
        self.assertEqual(clean(project), [])

    def test_red2_done_holder_finishes_and_resumes_parked_work(self) -> None:
        """Finishing a DONE holder resumes parked work at its saved phase."""
        project = self.make_project()
        parked, request = self.terminal_holder(project, "## DONE")

        holder = tickets(project)[request]
        restored = tickets(project)[parked]
        self.assertEqual(holder["section"], "## DONE")
        self.assertEqual(restored["section"], "## DOING")
        for field in ("blocker", "blocker_scope", "blocked_on", "resume_phase",
                      "resume_transition_from"):
            self.assertNotIn(field, restored["fields"], restored["fields"])

        state = self.state(project)
        self.assertEqual(state["phase"], "VERIFY")
        self.assertEqual(state["task"], parked)
        self.assertEqual(state["next_action"], f"PHASE VERIFY {parked}")
        self.assertEqual(clean(project), [])

    def test_red3_live_doing_holder_still_demotes(self) -> None:
        """Regression guard: the T-1473 mid-flight arm is unchanged."""
        project = self.make_project()
        parked, request = self.paused(project)
        self.assertTrue(apply_claim(project, request, AGENT).ok)

        result = self.release(project, parked, request)
        self.assertTrue(result.ok, result.to_dict())
        holder = tickets(project)[request]
        self.assertEqual(holder["section"], "## TODO")
        self.assertNotIn("owner", holder["fields"], holder["fields"])
        self.assertEqual(clean(project), [])

    def test_red4_foreign_live_doing_holder_refuses_without_writes(self) -> None:
        """A seat cannot be handed back while another seat owns its live holder."""
        project = self.make_project()
        parked, request = self.paused(project)
        claimed = apply_claim(project, request, OTHER, explicit=True)
        self.assertTrue(claimed.ok, claimed.to_dict())
        holder = tickets(project)[request]
        self.assertEqual(holder["section"], "## DOING")
        self.assertEqual(holder["fields"].get("owner"), OTHER)
        before = self.files(project)

        result = self.release(project, parked, request)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "TICKET_NOT_WORKABLE", result.to_dict())
        self.assertIn("live foreign claim", result.message)
        self.assertEqual(
            self.files(project), before
        )

    def test_red5_terminal_holder_does_not_bypass_a_dependency(self) -> None:
        """The release is not a dependency bypass: an unmet need still refuses."""
        project = self.make_project()
        parked, request = self.terminal_holder(project, "## BLOCKED")
        other = self.add(project, "a dependency the parked Work still needs")
        board_path = project / ".saipen" / "BOARD.md"
        board = board_path.read_text(encoding="utf-8")
        board_path.write_text(
            board.replace(f"needs: {request}", f"needs: {request},{other}", 1),
            encoding="utf-8",
        )
        self.assertIn(other, tickets(project)[parked]["needs"])
        before = (board_text(project), self.log_text(project))

        result = self.release(project, parked, request)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "TICKET_NOT_WORKABLE", result.to_dict())
        self.assertEqual(before, (board_text(project), self.log_text(project)))
        self.assertEqual(tickets(project)[parked]["section"], "## BLOCKED")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
