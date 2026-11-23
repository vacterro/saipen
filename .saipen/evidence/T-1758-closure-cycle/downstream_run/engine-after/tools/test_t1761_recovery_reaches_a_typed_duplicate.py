"""T-1761: recovery reaches a typed head that also duplicates an id.

Two rules met and neither could move. `reconcile` aims no BOARD repair through
a duplicated id, so the duplicate-id decision comes first (T-1382); and no
operation builds on an unauthorized head (T-1671), so that decision was
refused. `recover` printed a command the engine then refused, nothing moved,
and an executor working on such a project edited the engine instead
(2026-10-13, .saipen/evidence/foreign-edit-20261014-reconcile/).

The decision now runs over such a head and carries what it looked past: the
rows that head had closed, and the new name of a record it renamed while that
record sat under `## DONE`. Its own event therefore never becomes the floor
that buries a typed closure, and `recover` reopens it next. A record a hand
typed under `## DONE` behind a live id is a row too.
"""

from __future__ import annotations

import re
import shutil
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
import test_t1671_lifecycle_authority as typed  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

from saipen_engine import lifecycle_authority, operations  # noqa: E402
from saipen_engine.board import duplicate_records, parse_board  # noqa: E402

AGENT = typed.AGENT
UNAUTHORIZED = lifecycle_authority.UNAUTHORIZED
AUTHORIZED = lifecycle_authority.AUTHORIZED
DUPLICATE = (
    "- [ ] T-050 [P2] first record of the duplicated id | verify: probe\n"
    "- [ ] T-050 [P2] second record of the duplicated id | verify: probe\n"
)


def setUpModule() -> None:
    isolate_host_session()


class RouteFixture(unittest.TestCase):
    def setUp(self):
        self.root = typed._project()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.board_path = self.root / ".saipen" / "BOARD.md"

    def cli(self, *args):
        return probes.cli(self.root, AGENT, *args)

    def board(self) -> dict:
        return parse_board(self.board_path.read_text(encoding="utf-8"))

    def log(self) -> str:
        return (self.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")

    def verdict(self) -> tuple:
        docs, _state, _board, _tail = operations._read(
            self.root, observe=operations.TYPED_HEAD_QUARANTINE_OBSERVABLE
        )
        lifecycle = docs["_lifecycle"]
        rows = sorted({f["ticket"] for f in lifecycle["findings"] if f.get("ticket")})
        return lifecycle["status"], rows

    def duplicate_beside(self) -> None:
        text = self.board_path.read_text(encoding="utf-8")
        self.assertEqual(text.count("## TODO\n"), 1, text)
        self.board_path.write_text(
            text.replace("## TODO\n", "## TODO\n" + DUPLICATE), encoding="utf-8", newline="\n"
        )

    def type_a_second_record(self, *, with_lines: bool) -> None:
        """A hand closes a live id without moving its row: a second T-001
        record under `## DONE`, and (with_lines) the LOG lines and the marker
        that vouch for it."""
        if with_lines:
            probes.append_log(
                self.root, "T-001", AGENT,
                "RUN: verify -> PASS [target: T-001] conf: high -- typed by hand",
            )
            probes.append_log(self.root, "T-001", AGENT, "DEC: T-001 DONE; typed by hand")
        text = self.board_path.read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if "T-001" in line)
        done = re.sub(r"^- \[.\]", "- [x]", row) + " | closure_mode: own_patch"
        self.board_path.write_text(
            text.replace("## DONE\n", "## DONE\n" + done + "\n"), encoding="utf-8", newline="\n"
        )
        if with_lines:
            typed._state_field(self.root, "last_event", str(typed._log_tail(self.root)))

    def decide(self) -> dict:
        """Run the first decision `recover` prints; it must be the next step."""
        asked = self.cli("recover")
        self.assertEqual(asked.get("code"), "OPERATOR_DECISION_REQUIRED", asked)
        choice = asked["duplicate_id_decision"]["choices"][0].split()
        self.assertEqual(choice[:3], ["saipen", "recover", "--resolve-duplicate-id"], asked)
        decided = self.cli(*choice[1:])
        self.assertEqual(decided.get("code"), "DUPLICATE_ID_RESOLVED", decided)
        return decided

    def reopen(self) -> None:
        """The approval-gated repair `recover` names next, as the operator runs it."""
        plan = self.cli("recover")
        self.assertEqual(plan.get("code"), "RECONCILE_REAUTH_REQUIRED", plan)
        route = str(plan.get("canonical_next_command") or "").split()
        self.assertEqual(route[:3], ["saipen", "recover", "--apply-approved-repair"], plan)
        applied = self.cli(*route[1:])
        self.assertEqual(applied.get("code"), "REPAIRED", applied)


class TypedHeadBesideADuplicateTests(RouteFixture):
    def test_the_printed_decision_runs_and_the_typed_closure_is_not_buried(self):
        self.duplicate_beside()
        typed._type_the_lifecycle(self.root)
        self.assertEqual(self.verdict(), (UNAUTHORIZED, ["T-001"]))
        before = self.log()
        self.decide()
        added = self.log()[len(before):]
        self.assertIn("[op: duplicate-id-", added)
        self.assertIn(lifecycle_authority.carry_note(["T-001"]), added)
        self.assertEqual(self.verdict(), (UNAUTHORIZED, ["T-001"]))
        self.reopen()
        self.assertEqual(self.verdict(), (AUTHORIZED, []))
        board = self.board()
        self.assertEqual(board["errors"], [])
        self.assertEqual(board["tickets"]["T-001"]["section"], "## TODO")
        self.assertEqual(self.cli("recover").get("code"), "CLEAN")
        self.assertEqual(typed._lifecycle_fails(self.root), [])

    def test_a_decision_on_a_head_operations_wrote_carries_nothing(self):
        self.duplicate_beside()
        records = duplicate_records(self.board_path.read_text(encoding="utf-8"), "T-050")
        before = self.log()
        decided = self.cli(
            "recover", "--resolve-duplicate-id", "T-050",
            "--keep", records[0]["digest"], "--reassign", records[1]["digest"],
        )
        self.assertEqual(decided.get("code"), "DUPLICATE_ID_RESOLVED", decided)
        added = self.log()[len(before):]
        self.assertIn("[op: duplicate-id-", added)
        self.assertNotIn(lifecycle_authority.CARRY_MARKER, added)
        self.assertEqual(self.verdict(), (AUTHORIZED, []))


class TypedRecordBehindALiveIdTests(RouteFixture):
    def follow_the_renamed_record(self) -> None:
        self.assertEqual(self.verdict(), (UNAUTHORIZED, ["T-001"]))
        self.decide()
        board = self.board()
        self.assertEqual(board["errors"], [])
        renamed = [name for name, row in board["tickets"].items() if row["section"] == "## DONE"]
        self.assertEqual(len(renamed), 1, board["tickets"])
        self.assertNotEqual(renamed[0], "T-001")
        # The typed closure changed its name and stays judged under the new one.
        self.assertEqual(self.verdict(), (UNAUTHORIZED, renamed))
        self.reopen()
        self.assertEqual(self.verdict(), (AUTHORIZED, []))
        board = self.board()
        self.assertEqual(board["tickets"][renamed[0]]["section"], "## TODO")
        self.assertEqual(board["tickets"]["T-001"]["section"], "## DOING")
        self.assertEqual(typed._lifecycle_fails(self.root), [])

    def test_typed_lines_and_a_second_record_are_followed_through_the_rename(self):
        self.type_a_second_record(with_lines=True)
        self.follow_the_renamed_record()

    def test_a_second_record_with_no_other_trace_is_judged_too(self):
        self.type_a_second_record(with_lines=False)
        self.follow_the_renamed_record()


class CarryBoundaryTests(RouteFixture):
    def test_a_typed_carry_clause_judges_nothing_an_operation_holds(self):
        # A hand can type the clause; it can only ask for a row to be looked
        # at, and an operation stands behind this one.
        log_path = self.root / ".saipen" / "LOG.md"
        tail = typed._log_tail(self.root)
        forged = (
            f"- 13.10.26 00:00 [E-{tail + 1}] [parent: E-{tail}] [T-001] [agent: {AGENT}] "
            f"[op: duplicate-id-{'0' * 32}] DEC: {lifecycle_authority.carry_note(['T-001'])}"
        )
        log_path.write_text(
            log_path.read_text(encoding="utf-8").rstrip("\n") + "\n" + forged + "\n",
            encoding="utf-8", newline="\n",
        )
        self.assertEqual(self.verdict(), (AUTHORIZED, []))
        self.assertTrue(self.cli("checkpoint", "RUN", "T-001", "a canonical line").get("ok"))
        self.assertEqual(self.verdict(), (AUTHORIZED, []))

    def test_only_an_unauthorized_verdict_has_rows_to_carry(self):
        finding = {"rule": lifecycle_authority.TERMINAL_UNBACKED, "ticket": "T-7"}
        marker = {"rule": lifecycle_authority.STATE_AHEAD}
        unauthorized = {"status": UNAUTHORIZED, "findings": [finding, marker]}
        self.assertEqual(lifecycle_authority.carried_rows(unauthorized), ["T-7"])
        self.assertEqual(lifecycle_authority.carried_rows(unauthorized, "T-12"), ["T-7", "T-12"])
        for verdict in (None, {"status": AUTHORIZED, "findings": []},
                        {"status": lifecycle_authority.UNAVAILABLE, "findings": []}):
            self.assertEqual(lifecycle_authority.carried_rows(verdict, "T-12"), [])


if __name__ == "__main__":
    unittest.main()
