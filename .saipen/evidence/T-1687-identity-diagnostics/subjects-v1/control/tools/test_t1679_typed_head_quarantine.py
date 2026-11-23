"""T-1679: a typed head that also breaks the ledger is still recoverable.

Measured live (AUDAPACK, 2026-10-08 01:55Z): the executor that typed its own
lifecycle also replaced one of its lines, so a later line named a parent that
no longer existed. `saipen recover` answered HISTORY_LEDGER_CORRUPT with
terminal disposition FORENSICALLY_UNRECOVERABLE and no command. The tail
quarantine could not help: it cuts after `STATE.last_event`, and the same hand
had moved that marker onto its own lines.

The newest event a journal record stands behind does not depend on the parent
chain. The quarantine now cuts there, its event names the `## DONE` rows the
cut lines had closed, and the T-1672 reconciliation reopens them.
"""

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1671_lifecycle_authority import (  # noqa: E402
    AGENT,
    _bytes,
    _state_field,
    _type_the_lifecycle,
)

from saipen_engine import lifecycle_authority  # noqa: E402
from saipen_engine import log as log_module  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.journal import OPS_DIR  # noqa: E402
from saipen_engine.log import foreign_tail_cut, read_history_snapshot  # noqa: E402

CLASS = lifecycle_authority.CLASS
QUARANTINE = "saipen recover quarantine-log-tail"


def setUpModule() -> None:
    isolate_host_session()


def _project() -> Path:
    """T-001 canonically claimed and in BUILD, in a project bound to THIS home.

    The immutable-ledger contract is enforced for a project whose
    `saipen_home` is the running install -- the shape of every real project --
    so the fixture names it before the first operation runs.
    """
    root = probes.fresh_project("t1679")
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    state = root / ".saipen" / "STATE.md"
    text = state.read_text(encoding="utf-8")
    home = str(TOOLS.parent).replace("\\", "/")
    state.write_text(
        text.replace("mode: full\n", f'mode: full\nsaipen_home: "{home}"\n'),
        encoding="utf-8", newline="\n",
    )
    for args in (("continue",), ("claim", "T-001"), ("transition", "BUILD", "T-001", "scout done")):
        answer = probes.cli(root, AGENT, *args)
        assert answer.get("ok"), (args, answer)
    return root


def _replace_a_typed_line(root: Path) -> int:
    """Drop the middle typed line: the last one now names a missing parent."""
    path = root / ".saipen" / "LOG.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    typed = [index for index, line in enumerate(lines) if "[op: " not in line and "[E-" in line]
    victim = typed[-2]
    number = int(re.search(r"\[E-(\d+)\]", lines[victim]).group(1))
    del lines[victim]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return number


class BrokenTypedHeadTests(unittest.TestCase):
    def setUp(self):
        self.root = _project()
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))

    def cli(self, *args):
        return probes.cli(self.root, AGENT, *args)

    def break_it(self, *, malformed_state: bool = False) -> dict:
        _type_the_lifecycle(self.root, keep_task=True)
        _replace_a_typed_line(self.root)
        if malformed_state:
            _state_field(self.root, "transition_from", "REPAIR")
        return _bytes(self.root)

    def test_recover_names_the_quarantine_and_the_two_commands_restore_the_project(self):
        for malformed_state in (False, True):
            with self.subTest(malformed_state=malformed_state):
                self.root = _project()
                self.addCleanup(lambda root=self.root: shutil.rmtree(root, ignore_errors=True))
                before = self.break_it(malformed_state=malformed_state)
                refused = self.cli("recover")
                self.assertEqual(refused.get("code"), "HISTORY_LEDGER_CORRUPT", refused)
                self.assertEqual(refused.get("canonical_next_command"), QUARANTINE, refused)
                self.assertNotEqual(
                    refused.get("terminal_disposition"), "FORENSICALLY_UNRECOVERABLE", refused
                )
                self.assertEqual(_bytes(self.root), before)

                cut = self.cli("recover", "quarantine-log-tail")
                self.assertEqual(cut.get("code"), "LOG_TAIL_QUARANTINED", cut)
                self.assertEqual(cut.get("journal_floor"), 5, cut)
                self.assertEqual(cut.get("quarantined_lines"), 2, cut)
                kept = (self.root / cut["evidence_path"]).read_bytes()
                self.assertEqual(kept, before["LOG.md"])
                log = _bytes(self.root)["LOG.md"].decode()
                self.assertNotIn("lifecycle records written by hand", log)
                last = log.strip().splitlines()[-1]
                self.assertIn("[op: quarantine-log-tail-", last)
                self.assertIn(lifecycle_authority.TYPED_HEAD_MARKER + " above E-5", last)
                self.assertIn(lifecycle_authority.ROWS_PHRASE + "T-001", last)
                # The typed STATE.task must not tag the event that replaces it.
                self.assertNotIn("[T-001]", last)

                plan = self.cli("recover")
                self.assertEqual(plan.get("code"), "RECONCILE_REAUTH_REQUIRED", plan)
                self.assertIn(lifecycle_authority.REPAIR_CLASS, str(plan.get("changed")), plan)
                route = str(plan.get("canonical_next_command") or "").split()
                self.assertEqual(
                    route[:3], ["saipen", "recover", "--apply-approved-repair"], plan
                )
                applied = self.cli(*route[1:])
                self.assertEqual(applied.get("code"), "REPAIRED", applied)
                after = _bytes(self.root)
                row = parse_board(after["BOARD.md"].decode())["tickets"]["T-001"]
                self.assertEqual(row["section"], "## TODO", row)
                self.assertFalse({"owner", "claim_time", "closure_mode"} & set(row["fields"]), row)
                self.assertIn("task: none", after["STATE.md"].decode())
                self.assertIn("transition_from: DONE", after["STATE.md"].decode())
                status = self.cli("status")
                self.assertTrue(status.get("ok"), status)
                self.assertEqual(status.get("top_workable_ticket"), "T-001", status)
                self.assertEqual(self.cli("recover").get("code"), "CLEAN")

    def test_between_the_two_commands_the_quarantined_rows_still_refuse(self):
        self.break_it()
        self.assertEqual(self.cli("recover", "quarantine-log-tail").get("code"),
                         "LOG_TAIL_QUARANTINED")
        status = self.cli("status")
        self.assertEqual(status.get("reason"), CLASS, status)
        self.assertEqual(
            [(f["rule"], f["ticket"]) for f in status["lifecycle_authority"]["findings"]],
            [(lifecycle_authority.TERMINAL_UNBACKED, "T-001")],
        )
        self.assertIn(CLASS, str(self.cli("checkpoint", "RUN", "T-001", "on top")))

    def test_a_typed_head_the_contract_accepts_is_not_cut(self):
        """Its lines stay in the LOG as history; reconciliation owns it (T-1672)."""
        _type_the_lifecycle(self.root)
        before = _bytes(self.root)
        answer = self.cli("recover", "quarantine-log-tail")
        self.assertFalse(answer.get("ok"), answer)
        self.assertIn("already passes", str(answer.get("message")), answer)
        self.assertEqual(_bytes(self.root), before)
        self.assertEqual(self.cli("recover").get("code"), "RECONCILE_REAUTH_REQUIRED")


class JournalBoundCutTests(unittest.TestCase):
    """`log.foreign_tail_cut` with and without the journal floor."""

    def setUp(self):
        self.root = _project()
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        _type_the_lifecycle(self.root, keep_task=True)
        self.dropped = _replace_a_typed_line(self.root)
        self.snapshot = read_history_snapshot(self.root)
        self.active = (self.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")

    def test_without_a_floor_the_typed_marker_makes_the_damage_unprovable(self):
        cut, reason = foreign_tail_cut(self.snapshot, self.active, 8)
        self.assertIsNone(cut)
        self.assertIn("nothing but blanks and comments follows", reason)

    def test_the_floor_below_the_marker_is_the_boundary(self):
        floor, head = lifecycle_authority.journal_floor(self.root, self.snapshot.events)
        self.assertEqual(floor, 5)
        self.assertEqual(sorted(event["event"] for event in head), [6, 8])
        cut, reason = foreign_tail_cut(self.snapshot, self.active, 8, journal_floor=floor)
        self.assertIsNone(reason)
        self.assertEqual((cut.journal_floor, cut.claimed_ids), (5, (6, 8)))
        self.assertTrue(cut.kept_text.rstrip().endswith("scout done"))
        self.assertEqual(cut.snapshot.tail, 5)

    def test_a_floor_at_or_above_the_marker_changes_nothing(self):
        for floor in (8, 9):
            cut, reason = foreign_tail_cut(self.snapshot, self.active, 8, journal_floor=floor)
            self.assertIsNone(cut)
            self.assertIn("nothing but blanks and comments follows", reason)

    def test_a_tail_above_a_real_checkpoint_with_no_ledger_is_still_possibly_genuine(self):
        shutil.rmtree(self.root / OPS_DIR.split("/ops")[0])
        floor, _head = lifecycle_authority.journal_floor(self.root, self.snapshot.events)
        self.assertIsNone(floor)
        cut, reason = foreign_tail_cut(self.snapshot, self.active, 5, journal_floor=floor)
        self.assertIsNone(cut)
        self.assertIn("may be a genuine event whose checkpoint never landed", reason)


class ClosureVocabularyTests(unittest.TestCase):
    def test_an_adoption_is_not_a_closure_and_an_attestation_is(self):
        self.assertEqual(lifecycle_authority._ATTESTATION, log_module.LEGACY_DONE_ATTESTATION)
        adopted = {"event": 2, "ticket": "T-1", "op_id": "reconcile-20261008000000000000",
                   "text": "LEGACY_ADOPTED T-1 -- no canonical allocation event"}
        attested = dict(adopted, event=3,
                        text=log_module.legacy_done_attestation_text("T-1"))
        closed = lifecycle_authority._closed_by_operation
        self.assertFalse(closed([adopted], "T-1", 9))
        self.assertTrue(closed([adopted, attested], "T-1", 9))

    def test_the_quarantine_note_round_trips_through_the_reader(self):
        note = lifecycle_authority.quarantine_note(5, 2, ["T-1", "T-22"])
        self.assertIn(lifecycle_authority.TYPED_HEAD_MARKER, note)
        self.assertEqual(lifecycle_authority._ROWS_RE.search(note).group(1), "T-1, T-22")
        self.assertIsNone(
            lifecycle_authority._ROWS_RE.search(lifecycle_authority.quarantine_note(5, 2, []))
        )


if __name__ == "__main__":
    unittest.main()
