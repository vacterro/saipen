"""A PROMOTED future gate's slice row survives a scrub, and can come back.

FG-0046 was promoted with T-1936 as its done slice. T-1936 finished at E-18545
and a canonical scrub pruned its DONE row: the retention rule read receipts,
references and the closing ledger, but not the future-gate ledger that resolves
its slice tickets on the BOARD. The next core gate then FAILed
"FG-0046 names slice ticket T-1936, which is not on BOARD" over a satisfied
slice, and no verb could re-add the row.

Held here in both directions: `select` keeps the row under a `gate` guard, and
the same selection without the gate set prunes it -- so the guard, not the
fixture, is what keeps it. The row an earlier scrub already moved stays
recoverable by identity, which is what makes the repair possible today.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import board_scrub as BS  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402

ROW = "- [x] T-1936 [P2] read-only account discovery | verify: it holds"
OTHER = "- [x] T-1937 [P2] unrelated closed record | verify: it holds"

BOARD = (
    "# BOARD\n"
    "\n"
    "## TODO\n"
    "\n"
    "## DOING\n"
    "\n"
    "## BLOCKED\n"
    "\n"
    "## DONE\n"
    "\n"
    f"{ROW}\n"
    f"{OTHER}\n"
)

EVENTS = [
    {"ticket": "T-1936", "op_id": "finish-5b957bca1bc64d879649387eabf68287"},
    {"ticket": "T-1937", "op_id": "finish-0123456789abcdef0123456789abcdef"},
]


def _gate(ticket: str, state: str = "PROMOTED") -> dict:
    return {"id": "FG-0046", "state": state, "slices": [{"ticket": ticket, "closure": "done"}]}


class GatePinnedRowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / ".saipen" / "future").mkdir(parents=True)

    def _write(self, gates) -> None:
        (self.root / BS.FUTURE_INDEX).write_text(
            json.dumps({"gates": gates}), encoding="utf-8"
        )

    def _select(self, gated) -> BS.Selection:
        tickets = parse_board(BOARD)["tickets"]
        return BS.select(tickets, EVENTS, set(), set(), gated)

    def test_a_promoted_gate_pins_its_slice_ticket(self) -> None:
        self._write([_gate("T-1936")])
        self.assertEqual(BS.gated_tickets(self.root), {"T-1936"})

    def test_an_unpromoted_gate_pins_nothing(self) -> None:
        self._write([_gate("T-1936", state="NEEDS_REVIEW")])
        self.assertEqual(BS.gated_tickets(self.root), set())

    def test_an_unreadable_ledger_pins_nothing(self) -> None:
        (self.root / BS.FUTURE_INDEX).write_text("{not json", encoding="utf-8")
        self.assertEqual(BS.gated_tickets(self.root), set())

    def test_only_ticket_ids_are_read(self) -> None:
        self._write([_gate("..")])
        self.assertEqual(BS.gated_tickets(self.root), set())

    def test_select_keeps_the_gated_row_under_a_gate_guard(self) -> None:
        self._write([_gate("T-1936")])
        selection = self._select(BS.gated_tickets(self.root))
        self.assertIn("T-1936", selection.kept)
        self.assertEqual(selection.kept["T-1936"], "gate")
        self.assertIn("T-1937", selection.pruned)

    def test_without_the_gate_set_the_same_row_is_pruned(self) -> None:
        # Red control: the ledger is the only thing keeping the row.
        selection = self._select(set())
        self.assertIn("T-1936", selection.pruned)
        self.assertNotIn("T-1936", selection.kept)

    def test_a_pruned_gate_row_is_recoverable_verbatim(self) -> None:
        self._write([_gate("T-1936")])
        evidence = self.root / BS.SCRUB_EVIDENCE_ROOT / "board-scrub-aaa"
        evidence.mkdir(parents=True)
        (evidence / "BOARD.md").write_text(ROW + "\n", encoding="utf-8")
        pruned_board = BOARD.replace(f"{ROW}\n", "")
        absent = BS.gated_tickets(self.root) - set(parse_board(pruned_board)["tickets"])
        found = BS.pruned_rows(self.root, absent)
        self.assertEqual(found["T-1936"][0], ROW)

    def test_the_restored_row_closes_the_original_finding(self) -> None:
        # The row a scrub moved comes back at the head of DONE, and the parsed
        # BOARD the future gate reads now names T-1936 again.
        restored = BS.restored_board_text(BOARD.replace(f"{ROW}\n", ""), [ROW])
        self.assertIn("T-1936", parse_board(restored)["tickets"])


if __name__ == "__main__":
    unittest.main()
