"""T-925: a reviewed claim needs a DURABLE terminal disposition.

The CLEAN scrub moves a closed Core row to SCRUB_EVIDENCE_ROOT and its closing
event stays in the LOG. `subs._terminal_tickets` read terminal state from the
live BOARD alone, so a pruned review row made `sub status` report
`reviewed_without_disposition` for a package whose Core disposition had really
happened: the intake/review linkage lost its proof to a hygiene operation.

Held here: an id the BOARD no longer carries resolves from the closing event,
a live row still wins over a historical closure, and with no closing event the
answer stays not-terminal (fail closed).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import subs  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def _close_log(root: Path, ticket: str, op: str = "finish-deadbeef") -> None:
    path = root / ".saipen" / "LOG.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + f"- 12.09.26 00:01 [E-101] [{ticket}] [agent: test-agent] [op: {op}] "
        "DEC: ticket finished via SAIPEN\n",
        encoding="utf-8",
    )


def _board(root: Path, text: str) -> None:
    (root / ".saipen" / "BOARD.md").write_text(text, encoding="utf-8")


def setUpModule() -> None:
    isolate_host_session()


class TerminalDurability(unittest.TestCase):
    def test_pruned_row_resolves_from_the_closing_event(self):
        root = fresh_project()
        _close_log(root, "T-1")
        self.assertTrue(subs._terminal_tickets(root, ("T-1",))["T-1"])

    def test_without_a_closing_event_the_answer_stays_false(self):
        root = fresh_project()
        self.assertFalse(subs._terminal_tickets(root, ("T-1",))["T-1"])

    def test_live_row_wins_over_a_historical_closure(self):
        root = fresh_project()
        _board(root, "## DOING\n- [/] T-1 [P2] reopened\n## TODO\n## DONE\n## BLOCKED\n")
        _close_log(root, "T-1")
        self.assertFalse(subs._terminal_tickets(root, ("T-1",))["T-1"])

    def test_a_non_closing_event_is_not_a_closing_event(self):
        root = fresh_project()
        _close_log(root, "T-1", op="claim-deadbeef")
        self.assertFalse(subs._terminal_tickets(root, ("T-1",))["T-1"])

    def test_board_rows_are_read_without_extra_ids(self):
        root = fresh_project()
        _board(root, "## DOING\n## TODO\n## DONE\n- [x] T-2 [P3] closed\n## BLOCKED\n")
        self.assertTrue(subs._terminal_tickets(root)["T-2"])


if __name__ == "__main__":
    unittest.main()
