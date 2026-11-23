"""A slice ticket the LEDGER closed is not a broken link (FG-0046/T-1936).

`validate_future_gate` rule 6 asked only whether a slice's ticket is on the
live BOARD. A canonical scrub may move a closed record off that BOARD
(`board_scrub`): the row is never dropped, and before it may go the operation
requires a closing event in the ledger. FG-0046 named T-1936, which finished at
E-18545 and whose row a later scrub pruned, so a fully satisfied slice reported
"names slice ticket T-1936, which is not on BOARD" and the core gate stayed red
over a link the ledger proves.

The repair is not a widened rule. Rule 6 still FAILs a slice ticket nothing
closes: the BOARD question is answered by the ledger when the row is gone, and
only then. Pinned here in both directions, plus the unreadable-history half
that must keep failing rather than going quiet.
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


def _slice_errors(errors: list[str]) -> list[str]:
    return [error for error in errors if "not on BOARD" in error]


class PrunedSliceClosureTests(unittest.TestCase):
    def setUp(self):
        self.base, self.project = H._project()
        self.addCleanup(shutil.rmtree, self.base, True)
        H._write_gate(self.project, "gate.md", H._gate_doc("FG-0001"))
        gates.refresh(self.project)
        index = gates.load_index(self.project)
        for raw in index["gates"]:
            if raw["id"] == "FG-0001":
                raw["slices"] = [
                    {"ticket": "T-1936", "slice": raw["slice"], "closure": "done"}
                ]
        gates.write_index(self.project, index)
        # The ticket exists NOWHERE on the BOARD, exactly as a pruned row does.
        (self.project / ".saipen" / "BOARD.md").write_text(
            H.BOARD_PREAMBLE, encoding="utf-8"
        )
        self._append_log(
            "- 26.10.26 21:13 [E-18545] [parent: E-18544] [T-1936] [agent: "
            "saipen-cli] [op: finish-5b957bca1bc64d879649387eabf68287] DEC: "
            "ticket finished via SAIOPS -- completion (from SHIP)\n"
        )

    def _append_log(self, line: str) -> None:
        path = self.project / ".saipen" / "LOG.md"
        path.write_text(path.read_text(encoding="utf-8") + line, encoding="utf-8")

    def test_a_ledger_closed_slice_ticket_is_not_a_broken_link(self) -> None:
        self.assertEqual(
            _slice_errors(gates.validate_future_gate(self.project, H._tickets(self.project))["errors"]),
            [],
        )

    def test_a_slice_ticket_nothing_closes_still_fails(self) -> None:
        # The BOARD-only row is gone and the ledger holds no closing event, so
        # the link really is unproven -- the rule must keep biting.
        path = self.project / ".saipen" / "LOG.md"
        path.write_text(
            "- 26.10.26 21:13 [E-18545] [parent: E-18544] [T-1936] [agent: "
            "saipen-cli] [op: checkpoint-5b957bca1bc64d879649387eabf68287] RUN: "
            "verify -> PASS [target: T-1936]\n",
            encoding="utf-8",
        )
        errors = _slice_errors(
            gates.validate_future_gate(self.project, H._tickets(self.project))["errors"]
        )
        self.assertTrue(errors, "an unproven slice ticket must still be reported")
        self.assertIn("T-1936", errors[0])

    def test_an_unreadable_ledger_keeps_the_rule_biting(self) -> None:
        # Failure closed: history that cannot be read proves nothing, and a
        # validation error that goes quiet is worse than one that fires.
        original = gates._closed_in_history

        def _unreadable(root, ticket_ids):
            return set()

        gates._closed_in_history = _unreadable
        try:
            errors = _slice_errors(
                gates.validate_future_gate(self.project, H._tickets(self.project))["errors"]
            )
        finally:
            gates._closed_in_history = original
        self.assertTrue(errors)

    def test_a_live_board_row_needs_no_ledger_lookup(self) -> None:
        # The positive control for the whole family: a ticket still on the
        # BOARD is answered by the BOARD, and the ledger half is never reached.
        H._done(self.project, "T-1936")
        index = gates.load_index(self.project)
        for raw in index["gates"]:
            if raw["id"] == "FG-0001":
                raw["slices"] = [
                    {"ticket": "T-1936", "slice": raw["slice"], "closure": "done"}
                ]
        gates.write_index(self.project, index)
        self.assertEqual(
            _slice_errors(gates.validate_future_gate(self.project, H._tickets(self.project))["errors"]),
            [],
        )


if __name__ == "__main__":
    unittest.main()