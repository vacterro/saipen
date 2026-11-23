"""DONE/none writers persist what the ONE gate chain admits.

Measured (T-2083) after T-2082 closed: `_plan_finish_ticket` routed with
`route_next` only. On a CURRENT_FAIL receipt it stored
`next_action: "saipen continue"`, while `router.gate_route` on the same bytes
refused it (`CONFORMANCE_UNHEALTHY`, `conformance-remediation`, `terminal:
True`). With a STALE_FAIL receipt the crew writer stored `saipen crew` while
the gate refused the same route and NAMED its repair (`saipen validate`).

Both are the same defect on a second writer family: a host that follows
STATE.next_action re-dispatches a command the read surfaces refuse, so the
retry is a stall. The contract pinned here is the gate's own answer:

  * the gate names an executable repair -> that repair is stored
    (STALE_FAIL/NOT_RUN crew -> `saipen validate`);
  * the gate refuses with no executable action -> the writer stores a typed
    `WAIT:` under the closed section 1.2 grammar, never the refused command;
  * the gate does not rewrite the route -> the route stands.

Run standalone:
    python -m unittest tools.test_writer_route_projection
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
for _entry in (str(TOOLS), str(TOOLS.parent)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import conformance  # noqa: E402
from saipen_engine import operations  # noqa: E402
from saipen_engine import state as S  # noqa: E402
from test_t1412_conformance_truth import T1412Base, write_receipt  # noqa: E402

AGENT = "tester"


class RouteProjectionBase(T1412Base):
    def sole_receipt(self, root: Path, verdict: str) -> None:
        """One receipt, bound to the current bytes -- the fixture's premise."""
        receipt_dir = root / conformance.RECEIPT_DIRNAME
        for stale in receipt_dir.glob("*.json"):
            stale.unlink()
        write_receipt(root, verdict)

    def next_action(self, root: Path) -> str:
        state = S.parse_state(
            (root / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")
        )
        return str(state.get("next_action") or "")

    def assert_wait(self, action: str) -> None:
        self.assertTrue(action.startswith("WAIT:"), action)
        self.assertIsNone(S.wait_grammar_error(action), action)
        # A refused route is not a pre-authorized stop.
        self.assertNotIn(S.parse_wait(action), {"init"})

    def ship_project(self, name: str) -> Path:
        """A valid project standing at the closure edge with one DOING ticket.

        The fixture is written directly, as `ticket done` receives it: running
        a real BUILD edge here would make this verifier depend on a validator
        subprocess that the regression sandbox does not materialize.
        """
        root = self.make_project(name)
        stamp = "2026-09-19T21:00:00Z"
        state = S.patch_state(
            (root / ".saipen" / "STATE.md").read_text(encoding="utf-8"),
            {
                "phase": "SHIP",
                "task": "T-7",
                "next_action": "PHASE SHIP T-7",
                "transition_from": "REVIEW",
                "last_event": 2,
            },
        )
        (root / ".saipen" / "STATE.md").write_text(
            state, encoding="utf-8", newline="\n"
        )
        # The closure gate wants the ticket's current-cycle VERIFY boundary and
        # a PASS after it; an event's taxonomy is the RUN marker, so the
        # boundary is the RUN body "transition to VERIFY".
        (root / ".saipen" / "LOG.md").write_text(
            "# LOG\n\n"
            "- 19.09.26 21:00 [E-001] [T-7] [agent: tester] "
            "RUN: transition to VERIFY -- fixture cycle\n"
            "- 19.09.26 21:01 [E-002] [T-7] [agent: tester] "
            "RUN: fixture proof -> PASS conf: high\n",
            encoding="utf-8",
            newline="\n",
        )
        (root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n"
            f"- [/] T-7 [P1] closure projection probe | verify: proof "
            f"| owner: {AGENT} | claim_time: {stamp}\n"
            "## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
            newline="\n",
        )
        return root


class ConvergeEntryProjectsTheGate(RouteProjectionBase):
    def test_a_named_repair_is_stored_instead_of_the_refused_route(self):
        root = self.make_project("entry-not-run")
        result = operations.set_converge_intent(root, AGENT, "crew")
        self.assertTrue(result.ok, result.message)
        action = self.next_action(root)
        self.assertNotEqual(action, "saipen crew")
        self.assertEqual(action, "saipen validate")

    def test_a_terminal_refusal_stores_a_typed_wait(self):
        root = self.make_project("entry-fail")
        self.sole_receipt(root, "FAIL")
        result = operations.set_converge_intent(root, AGENT, "crew")
        self.assertTrue(result.ok, result.message)
        self.assert_wait(self.next_action(root))

    def test_a_healthy_receipt_keeps_the_route(self):
        root = self.make_project("entry-pass")
        self.sole_receipt(root, "PASS")
        result = operations.set_converge_intent(root, AGENT, "crew")
        self.assertTrue(result.ok, result.message)
        self.assertEqual(self.next_action(root), "saipen crew")


class ClosureProjectsTheGate(RouteProjectionBase):
    def test_finish_never_stores_a_refused_idle_command(self):
        root = self.ship_project("finish-fail")
        ticket = "T-7"
        self.sole_receipt(root, "FAIL")
        result = operations.finish_ticket(root, ticket, AGENT)
        self.assertTrue(result.ok, result.message)
        action = self.next_action(root)
        self.assertNotEqual(action, "saipen continue")
        self.assertNotEqual(action, "saipen crew")
        self.assert_wait(action)
        # The operation's report and the committed bytes are one fact.
        self.assertEqual(result.data.get("next_action"), action)

    def test_finish_on_a_healthy_receipt_keeps_the_idle_route(self):
        root = self.ship_project("finish-pass")
        ticket = "T-7"
        self.sole_receipt(root, "PASS")
        result = operations.finish_ticket(root, ticket, AGENT)
        self.assertTrue(result.ok, result.message)
        self.assertEqual(self.next_action(root), "saipen continue")
        self.assertEqual(result.data.get("next_action"), "saipen continue")


if __name__ == "__main__":
    unittest.main(verbosity=2)
