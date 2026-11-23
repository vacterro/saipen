"""T-1961: a slice ticket CLEAN legally pruned is resolved from the LOG.

`phases/clean.md` step 1 moves a closed BOARD row to `SCRUB_EVIDENCE_ROOT`, and
`board_scrub.closed_in_history` reads the durable LOG closing event as the
proof that Work exists at all -- the fact `subs._terminal_tickets` has read
since T-925. `future_gate` rule 6 alone still demanded the physical row, so the
sanctioned hygiene step turned a green validator red: measured 2026-10-30 on
this repository, one CLEAN entry moved 298 closed records and `validate` went
from 4 problems to 5, the new one naming FG-0046's slice T-1936.

Held here, in both directions: a pruned slice ticket stays resolved while the
history proves its closure, and the same ticket is still a finding when the
history carries no closing operation for it, when there is no history at all,
and when the record names a ticket that never existed.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from saipen_engine import future_gate as gates  # noqa: E402


def _closing(ticket: str, op_id: str = "finish-t1961") -> dict:
    """One durable closing event, shaped as `closed_in_history` reads it."""
    return {"ticket": ticket, "op_id": op_id}


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.base, self.project = H._project()
        self.addCleanup(shutil.rmtree, self.base, True)
        H._write_gate(self.project, "gate.md", H._gate_doc("FG-0001", "A gate"))
        gates.refresh(self.project)
        index = gates.load_index(self.project)
        for raw in index["gates"]:
            if raw["id"] == "FG-0001":
                # The binding promotion made, pointing at a row the scrub left.
                raw["slices"] = [
                    {"ticket": "T-001", "slice": raw["slice"], "closure": "done"}
                ]
                raw["state"] = gates.PROMOTED
        gates.write_index(self.project, index)

    def _findings(self, history_events):
        return gates.validate_future_gate(
            self.project,
            H._tickets(self.project),
            history_events=history_events,
        )

    def _slice_errors(self, history_events) -> list[str]:
        return [
            error
            for error in self._findings(history_events)["errors"]
            if "slice ticket" in error and "not on BOARD" in error
        ]


class PrunedSliceIsResolvedTests(_Fixture):
    def test_a_slice_ticket_pruned_by_clean_is_not_a_finding(self):
        self.assertEqual(self._slice_errors([_closing("T-001")]), [])

    def test_a_slice_ticket_absent_from_the_board_and_history_still_fails(self):
        errors = self._slice_errors([])
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("FG-0001 names slice ticket T-001", errors[0])

    def test_no_history_at_all_is_fail_closed(self):
        errors = self._slice_errors(None)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("not on BOARD", errors[0])

    def test_a_non_closing_event_does_not_resolve_the_ticket(self):
        # A claim or a transition is not a closure: the row must not disappear
        # on the strength of the Work merely having been touched.
        errors = self._slice_errors([{"ticket": "T-001", "op_id": "claim-t1961"}])
        self.assertEqual(len(errors), 1, errors)

    def test_a_closing_event_for_another_ticket_does_not_resolve_this_one(self):
        errors = self._slice_errors([_closing("T-002")])
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("T-001", errors[0])

    def test_a_row_still_on_the_board_is_judged_by_its_section(self):
        # The resolution must not shadow the ordinary path: a live row bound to
        # an unpromoted gate stays a duplicate finding, even while the pruned
        # T-001 is resolved from the same history read.
        live = H._add(self.project, "work whose text names no gate")
        index = gates.load_index(self.project)
        for raw in index["gates"]:
            if raw["id"] == "FG-0001":
                raw["state"] = gates.DEFERRED
                raw["slices"] = raw["slices"] + [
                    {"ticket": live, "slice": raw["slice"], "closure": gates.UNRESOLVED}
                ]
        gates.write_index(self.project, index)
        findings = self._findings([_closing("T-001")])
        self.assertEqual(
            [e for e in findings["errors"] if "slice ticket" in e and "not on BOARD" in e], []
        )
        self.assertEqual(
            len([e for e in findings["errors"] if "works on future gate" in e]), 1,
            findings["errors"],
        )


if __name__ == "__main__":
    unittest.main()
