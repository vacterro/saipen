"""T-1673: a row moved into DONE in BOARD.md alone is not invisible.

T-1672's lifecycle authority judges what a hand writes ABOVE the journal floor:
a LOG head with no operation record, a STATE marker moved past it. An edit of
BOARD.md alone -- a row moved under `## DONE` with a typed `closure_mode`, no
LOG line, STATE untouched -- named nothing above the floor, so status stayed
valid and every verb built on it. The repair: every committed plan that writes
BOARD.md leaves a terminal baseline, and a ticket in the live `## DONE` set and
not in the baseline, with no closure operation behind it, is
`terminal-without-operation`.

The CLI half drives the real engine on a project with a real ledger; the unit
half pins the boundaries the CLI cannot reach cheaply.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1671_lifecycle_authority import AGENT, _project  # noqa: E402

from saipen_engine import lifecycle_authority  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.journal import OPS_DIR  # noqa: E402

CODE = lifecycle_authority.CODE
CLASS = lifecycle_authority.CLASS
CANON = ("STATE.md", "BOARD.md", "LOG.md")


def setUpModule() -> None:
    isolate_host_session()


def _bytes(root: Path) -> dict:
    return {name: (root / ".saipen" / name).read_bytes() for name in CANON}


def _move_into_done(root: Path, ticket: str) -> None:
    """What the hand wrote: the row, checked, under ## DONE -- and nothing else."""
    board = root / ".saipen" / "BOARD.md"
    text = board.read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if f" {ticket} " in row)
    text = text.replace(line + "\n", "")
    done = re.sub(r"^- \[.\]", "- [x]", line) + " | closure_mode: own_patch"
    board.write_text(
        text.replace("## DONE\n", "## DONE\n" + done + "\n"), encoding="utf-8", newline="\n"
    )


class BoardOnlyMoveTests(unittest.TestCase):
    def setUp(self):
        self.root = _project()
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        added = self.cli("ticket", "add", "P2", "second piece of work", "--verify", "it works")
        self.assertTrue(added.get("ok"), added)
        self.ticket = added["ticket"]

    def cli(self, *args):
        return probes.cli(self.root, AGENT, *args)

    def test_a_board_only_move_is_refused_by_every_entry_and_writes_nothing(self):
        _move_into_done(self.root, self.ticket)
        before = _bytes(self.root)
        status = self.cli("status")
        self.assertFalse(status.get("ok"), status)
        self.assertEqual((status.get("code"), status.get("reason")), (CODE, CLASS), status)
        findings = status["lifecycle_authority"]["findings"]
        self.assertEqual(
            [(f["rule"], f["ticket"], f.get("origin")) for f in findings],
            [(lifecycle_authority.TERMINAL_UNBACKED, self.ticket, "board-only")],
        )
        for args in (
            ("transition", "VERIFY", "T-001", "build done"),
            ("checkpoint", "RUN", "T-001", "a note after the fact"),
            ("ticket", "add", "P2", "more work", "--verify", "it works"),
            ("claim", self.ticket),
        ):
            with self.subTest(args=args):
                answer = self.cli(*args)
                self.assertFalse(answer.get("ok"), answer)
                self.assertEqual(answer.get("code"), CODE, answer)
                self.assertEqual(_bytes(self.root), before)

    def test_recovery_reopens_the_row_and_status_is_valid_again(self):
        _move_into_done(self.root, self.ticket)
        before = _bytes(self.root)
        plan = self.cli("continue")
        self.assertEqual(plan.get("code"), "RECONCILE_REAUTH_REQUIRED", plan)
        route = str(plan.get("canonical_next_command") or "").split()
        self.assertEqual(route[:3], ["saipen", "recover", "--apply-approved-repair"], plan)
        self.assertEqual(_bytes(self.root), before)
        applied = self.cli(*route[1:])
        self.assertEqual(applied.get("code"), "REPAIRED", applied)
        after = _bytes(self.root)
        row = parse_board(after["BOARD.md"].decode())["tickets"][self.ticket]
        self.assertEqual(row["section"], "## TODO", row)
        self.assertNotIn("closure_mode", row["fields"], row)
        added = after["LOG.md"][len(before["LOG.md"]) :].decode()
        self.assertIn("edit of BOARD.md", added)
        status = self.cli("status")
        self.assertTrue(status.get("ok"), status)

    def test_a_board_edit_that_moves_no_ticket_is_not_refused(self):
        board = self.root / ".saipen" / "BOARD.md"
        text = board.read_text(encoding="utf-8")
        board.write_text(
            text.replace("second piece of work", "second piece of work, reworded"),
            encoding="utf-8",
            newline="\n",
        )
        status = self.cli("status")
        self.assertTrue(status.get("ok"), status)

    def test_the_baseline_follows_every_committed_board_write(self):
        baseline = json.loads(
            (self.root / lifecycle_authority.TERMINAL_BASELINE).read_text(encoding="utf-8")
        )
        live = (self.root / ".saipen" / "BOARD.md").read_bytes()
        self.assertEqual(baseline["board_sha256_16"], lifecycle_authority._board_digest(live))
        blocked = self.cli("ticket", "block", self.ticket, "waits on something")
        self.assertTrue(blocked.get("ok"), blocked)
        again = json.loads(
            (self.root / lifecycle_authority.TERMINAL_BASELINE).read_text(encoding="utf-8")
        )
        self.assertNotEqual(again["board_sha256_16"], baseline["board_sha256_16"])


def _event(number: int, ticket: str | None, line: str, op_id: str | None = None) -> dict:
    taxonomy, text = line.split(": ", 1)
    return {"event": number, "ticket": ticket, "text": text, "op_id": op_id, "taxonomy": taxonomy}


class BaselineBoundaryTests(unittest.TestCase):
    """`assess` with a baseline written for the case."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="t1673-unit-"))
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        (self.root / ".saipen").mkdir()
        self.claim, self.finish = "claim-" + "a" * 32, "finish-" + "b" * 32
        for op_id in (self.claim, self.finish):
            os.makedirs(self.root / OPS_DIR / op_id)
        self.events = [
            _event(1, "T-1", "DEC: claimed via SAIOPS -- owner x", self.claim),
            _event(2, "T-1", "DEC: ticket finished via SAIOPS -- completion", self.finish),
        ]

    def write_board(self, done: list[str], todo: list[str]) -> dict:
        lines = ["# Board", "## DOING", "## TODO"]
        lines += [f"- [ ] {tid} work | verify: v" for tid in todo]
        lines.append("## DONE")
        lines += [f"- [x] {tid} work | verify: v" for tid in done]
        lines.append("## BLOCKED")
        text = "\n".join(lines) + "\n"
        (self.root / ".saipen" / "BOARD.md").write_text(text, encoding="utf-8", newline="\n")
        return parse_board(text)

    def assess(self, board):
        return lifecycle_authority.assess(self.root, {"last_event": 2}, board, self.events)

    def test_no_baseline_is_no_finding(self):
        board = self.write_board(done=["T-2"], todo=[])
        self.assertEqual(self.assess(board)["findings"], [])

    def test_a_row_a_closure_operation_closed_is_never_a_board_only_move(self):
        self.write_board(done=[], todo=["T-1", "T-2"])
        lifecycle_authority.record_terminal(self.root)
        board = self.write_board(done=["T-1", "T-2"], todo=[])
        found = self.assess(board)["findings"]
        self.assertEqual([(f["ticket"], f.get("origin")) for f in found], [("T-2", "board-only")])

    def test_an_unchanged_board_is_not_judged_whatever_the_baseline_says(self):
        board = self.write_board(done=["T-2"], todo=[])
        lifecycle_authority.record_terminal(self.root)
        self.assertEqual(self.assess(board)["findings"], [])

    def test_an_unreadable_baseline_is_no_finding(self):
        self.write_board(done=[], todo=["T-2"])
        lifecycle_authority.record_terminal(self.root)
        (self.root / lifecycle_authority.TERMINAL_BASELINE).write_text("{", encoding="utf-8")
        board = self.write_board(done=["T-2"], todo=[])
        self.assertEqual(self.assess(board)["findings"], [])


if __name__ == "__main__":
    unittest.main()
