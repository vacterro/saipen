"""T-1641: ownership of future-gate work is the slice record, never a mention.

`validate_future_gate` FAILed "BOARD ticket T-x works on future gate FG-y" and
`readiness` held the gate back whenever the gate id appeared anywhere in a live
ticket's text. A defect report that cited a gate (T-1638 and then T-1641 itself
citing FG-0046) was therefore flagged as a duplicate implementation ticket, and
the core gate stayed red for as long as the report was open.

The machine fact is the slice record promotion writes (`record_slice`). These
cases pin both directions: a mention owns nothing, and a binding is still
judged -- on an unpromoted gate, across two gates, twice on one slice.
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


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.base, self.project = H._project()
        self.addCleanup(shutil.rmtree, self.base, True)

    def _gate(self, gate_id: str = "FG-0001", name: str = "gate.md", title: str = "A gate") -> None:
        H._write_gate(self.project, name, H._gate_doc(gate_id, title))
        gates.refresh(self.project)

    def _bind(self, gate_id: str, records: list, state: str | None = None) -> None:
        """Write slice records straight into the index: a binding promotion did not make."""
        index = gates.load_index(self.project)
        for raw in index["gates"]:
            if raw["id"] == gate_id:
                raw["slices"] = [
                    {"ticket": tid, "slice": raw["slice"], "closure": closure}
                    for tid, closure in records
                ]
                if state:
                    raw["state"] = state
        gates.write_index(self.project, index)

    def _findings(self) -> dict:
        return gates.validate_future_gate(self.project, H._tickets(self.project))

    def _ownership_errors(self) -> list[str]:
        return [
            error
            for error in self._findings()["errors"]
            if "works on future gate" in error
            or "bound as a slice" in error
            or "binds one slice" in error
        ]


class MentionIsNotOwnershipTests(_Fixture):
    def test_a_ticket_that_only_cites_a_gate_does_not_fail_validation(self):
        self._gate()
        H._add(self.project, "defect report: the readiness of FG-0001 reads prose")
        self.assertEqual(self._ownership_errors(), [])

    def test_a_ticket_that_only_cites_a_gate_does_not_hold_it_back(self):
        self._gate()
        H._add(self.project, "defect report: the readiness of FG-0001 reads prose")
        tickets = H._tickets(self.project)
        report = gates.evaluate(self.project, tickets)
        self.assertEqual(report["next"], "FG-0001", report["evaluated"])
        self.assertTrue(gates.promote(self.project, "FG-0001", board_tickets=tickets)["ok"])

    def test_the_stored_reasons_stop_naming_a_citing_ticket(self):
        self._gate()
        tid = H._add(self.project, "defect report: the readiness of FG-0001 reads prose")
        gates.evaluate(self.project, H._tickets(self.project))
        stored = gates.get_gate(self.project, "FG-0001")
        self.assertFalse(any(tid in reason for reason in stored.reasons), stored.reasons)


class SliceRecordIsOwnershipTests(_Fixture):
    def test_a_live_ticket_bound_to_an_unpromoted_gate_fails(self):
        self._gate()
        tid = H._add(self.project, "work whose text names no gate")
        self._bind("FG-0001", [(tid, "done")])
        errors = self._ownership_errors()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn(f"BOARD ticket {tid} works on future gate FG-0001, which is", errors[0])

    def test_a_bound_live_ticket_holds_the_gate_back(self):
        self._gate()
        tid = H._add(self.project, "work whose text names no gate")
        self._bind("FG-0001", [(tid, "done")])
        tickets = H._tickets(self.project)
        report = gates.evaluate(self.project, tickets)
        self.assertIsNone(report["next"])
        promotion = gates.promote(self.project, "FG-0001", board_tickets=tickets)
        self.assertFalse(promotion["ok"])
        self.assertTrue(any(tid in reason for reason in promotion["reasons"]), promotion)

    def test_the_promoted_owner_is_not_a_finding(self):
        self._gate()
        from saipen import _execute_future_promotion

        payload, rc = _execute_future_promotion(self.project, "FG-0001", False)
        self.assertEqual(rc, 0, payload)
        self.assertEqual(
            gates.bound_tickets(gates.get_gate(self.project, "FG-0001")), [payload["ticket"]]
        )
        self.assertEqual(self._ownership_errors(), [])

    def test_a_ticket_bound_to_two_gates_fails(self):
        self._gate("FG-0001", "a.md", "First gate")
        self._gate("FG-0002", "b.md", "Second gate")
        tid = H._add(self.project, "work whose text names no gate")
        self._bind("FG-0001", [(tid, gates.UNRESOLVED)], gates.PROMOTED)
        self._bind("FG-0002", [(tid, gates.UNRESOLVED)], gates.PROMOTED)
        errors = self._ownership_errors()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn(f"BOARD ticket {tid} is bound as a slice of FG-0001, FG-0002", errors[0])

    def test_a_second_live_ticket_on_one_slice_is_the_duplicate(self):
        # A duplicate made outside promotion: the record binds a second ticket
        # to the slice the first one already holds.
        self._gate()
        first = H._add(self.project, "work whose text names no gate")
        second = H._add(self.project, "the same work, filed again")
        self._bind(
            "FG-0001", [(first, gates.UNRESOLVED), (second, gates.UNRESOLVED)], gates.PROMOTED
        )
        errors = self._ownership_errors()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn(f"future gate FG-0001 binds one slice to {first}, {second}", errors[0])

    def test_a_bound_ticket_that_is_done_holds_nothing(self):
        self._gate()
        H._done(self.project, "T-001")
        self._bind("FG-0001", [("T-001", "done")])
        self.assertEqual(self._ownership_errors(), [])
        report = gates.evaluate(self.project, H._tickets(self.project))
        self.assertEqual(report["next"], "FG-0001", report["evaluated"])


if __name__ == "__main__":
    unittest.main()
