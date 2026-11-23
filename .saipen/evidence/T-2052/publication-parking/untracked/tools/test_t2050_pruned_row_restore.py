"""T-2050: a pruned closed row an ACTIVE receipt still names is recoverable.

The validator FAILed `active receipt SRC-x references missing Work T-y` on rows
the 30.10.26 scrub moved. The scrub keeps the lines it removes verbatim, so the
row was never lost -- but nothing could put one back: `source recover` reported
the receipts as clean and no verb re-added a record, so the finding degraded to
ENGINEERING_REQUIRED and the gate stayed red with no action available.

Held here: the evidence reader returns the bytes the BOARD held (newest scrub
wins), the insertion keeps every other byte of the document, and the finding's
own message now carries a command the remediation table admits, so a red gate
names an executable repair instead of an engineering obligation.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import board_scrub as BS  # noqa: E402
from saipen_engine import remediation  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402

ROW_A = "- [x] T-1316 [P1] first closed record | verify: it holds | source_receipts: SRC-027"
ROW_B = "- [x] T-1320 [P2] second closed record | verify: it holds | needs: T-1316"

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
    "- [x] T-9000 [P2] a record that stayed | verify: it holds\n"
)


def _evidence(root: Path, op_id: str, rows) -> Path:
    target = root / BS.SCRUB_EVIDENCE_ROOT / op_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "BOARD.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return target / "BOARD.md"


class PrunedRowsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_returns_the_bytes_the_board_held(self) -> None:
        path = _evidence(self.root, "board-scrub-aaa", [ROW_A, ROW_B])
        found = BS.pruned_rows(self.root, ["T-1316"])
        self.assertEqual(found["T-1316"][0], ROW_A)
        self.assertEqual(found["T-1316"][1], path.relative_to(self.root).as_posix())

    def test_newest_scrub_wins(self) -> None:
        _evidence(self.root, "board-scrub-aaa", [ROW_A])
        newest = "- [x] T-1316 [P1] the same record later | verify: it holds"
        _evidence(self.root, "board-scrub-zzz", [newest])
        self.assertEqual(BS.pruned_rows(self.root, ["T-1316"])["T-1316"][0], newest)

    def test_only_rows_opening_with_the_ticket_are_matched(self) -> None:
        _evidence(
            self.root,
            "board-scrub-aaa",
            [
                "- [x] T-1316 [P1] real record",
                "- a note that mentions T-1316 inside its prose",
                "T-1316 without a record shape",
            ],
        )
        found = BS.pruned_rows(self.root, ["T-1316"])
        self.assertEqual(found["T-1316"][0], "- [x] T-1316 [P1] real record")

    def test_absent_ticket_is_not_invented(self) -> None:
        _evidence(self.root, "board-scrub-aaa", [ROW_A])
        self.assertEqual(BS.pruned_rows(self.root, ["T-4242"]), {})

    def test_malformed_ids_never_scan_for_a_prefix(self) -> None:
        _evidence(self.root, "board-scrub-aaa", [ROW_A])
        # A substring or a path fragment must never resolve to a record.
        self.assertEqual(BS.pruned_rows(self.root, ["T-131", "..", "T-1316x"]), {})


class RestoredBoardTextTest(unittest.TestCase):
    def test_inserts_at_the_head_of_done(self) -> None:
        new = BS.restored_board_text(BOARD, [ROW_A, ROW_B])
        lines = new.split("\n")
        head = lines.index("## DONE")
        self.assertEqual(lines[head + 1], ROW_A)
        self.assertEqual(lines[head + 2], ROW_B)
        self.assertEqual(lines[head + 3], "")

    def test_every_other_byte_is_preserved(self) -> None:
        new = BS.restored_board_text(BOARD, [ROW_A])
        self.assertEqual(new.replace(ROW_A + "\n", "", 1), BOARD)

    def test_crlf_is_kept(self) -> None:
        crlf = BOARD.replace("\n", "\r\n")
        new = BS.restored_board_text(crlf, [ROW_A])
        self.assertIn("\r\n" + ROW_A + "\r\n", new)
        self.assertEqual(new.replace(ROW_A + "\r\n", "", 1), crlf)

    def test_nothing_to_insert_returns_the_document(self) -> None:
        self.assertEqual(BS.restored_board_text(BOARD, []), BOARD)

    def test_refuses_without_a_closed_section(self) -> None:
        with self.assertRaises(ValueError):
            BS.restored_board_text("# BOARD\n\n## DOING\n", [ROW_A])

    def test_restored_edges_resolve_on_the_parsed_board(self) -> None:
        parsed = parse_board(BS.restored_board_text(BOARD, [ROW_A, ROW_B]))
        self.assertEqual(parsed["errors"], [])
        self.assertIn("T-1316", parsed["tickets"])
        self.assertEqual(parsed["tickets"]["T-1320"]["needs"], ["T-1316"])


class RemediationRegisterTest(unittest.TestCase):
    MESSAGE = (
        "active receipt SRC-027 references missing Work T-1316 -- saipen source "
        "recover --confirm re-inserts the row an earlier scrub moved"
    )

    def test_the_finding_message_yields_an_executable_repair(self) -> None:
        commands = remediation.extract_commands([self.MESSAGE])
        self.assertEqual(commands, ["saipen source recover --confirm"])

    def test_the_repair_resolves_to_a_registered_verb(self) -> None:
        resolved = remediation.resolve_command("saipen source recover --confirm")
        self.assertTrue(resolved["ok"], resolved)
        self.assertEqual((resolved["verb"], resolved["action"]), ("source", "recover"))

    def test_the_plain_survey_form_still_resolves(self) -> None:
        self.assertTrue(remediation.resolve_command("saipen source recover")["ok"])
        self.assertNotIn("saipen source recover", remediation.extract_commands([self.MESSAGE]))


if __name__ == "__main__":
    unittest.main()
