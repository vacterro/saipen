"""T-2096: the scrub warning and the scrub operation make ONE decision.

The validator's `board-soft-cap` finding called `board_scrub.select` without
the promoted-gate set, while `operations.scrub_board` passed it. A DONE row a
PROMOTED future gate pins was therefore counted as prunable by the warning and
kept by the operation: the warning asked for a scrub that would under-deliver,
or a synthetic board whose only large closed text is gate-pinned reported debt
no canonical route could clear.

Held here: both sides read `board_scrub.collect_inputs` and pass the SAME four
inputs to `select`; a gate-pinned 17 KB record produces no scrub-due; an
unreadable, unindexed, schema-drifted or malformed gate ledger is UNKNOWN to a
destructive caller instead of "no gates"; and the canonical CLEAN move keeps
the pruned bytes verbatim.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import board_scrub as BS  # noqa: E402
from saipen_engine import intake  # noqa: E402
from saipen_engine.operations import scrub_board  # noqa: E402

from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1640_board_scrub import (  # noqa: E402
    AGENT,
    _board,
    _done,
    _evidence,
    _findings,
    _ids,
    _project,
)

#: Big enough that a single closed row alone crosses the 16 KiB cap.
BIG = "gate-pinned closed implementation record text " * 380
GATE_ID = "FG-9001"
GATE_TICKET = "T-1936"


def setUpModule() -> None:
    isolate_host_session()


def _write_index(root: Path, *, marker: str = "saipen-future-index-v1",
                 schema: object = 2, gates: object = None) -> None:
    (root / ".saipen" / "future").mkdir(parents=True, exist_ok=True)
    index = {
        "marker": marker,
        "schema": schema,
        "gates": gates if gates is not None else [],
    }
    (root / BS.FUTURE_INDEX).write_text(json.dumps(index), encoding="utf-8")


def _gate(ticket: str, state: str = "PROMOTED") -> dict:
    return {
        "id": GATE_ID,
        "path": None,
        "title": "scrub eligibility parity fixture",
        "state": state,
        "machine_readable": True,
        "present": False,
        "slices": [{"ticket": ticket, "closure": "done"}],
    }


def _shared_selection(root: Path) -> BS.Selection:
    """The one path both the validator and the operation now walk."""
    from saipen_engine.board import parse_board
    from saipen_engine.log import read_history_snapshot

    tickets = parse_board(_board(root).decode("utf-8"))["tickets"]
    inputs = BS.collect_inputs(root)
    return BS.select(
        tickets,
        read_history_snapshot(root).events,
        inputs.active_receipts,
        inputs.receipt_works,
        inputs.gated,
    )


class SharedInputTests(unittest.TestCase):
    def test_a_promoted_gate_pins_the_same_row_for_both_sides(self) -> None:
        root = _project([_done("T-1", prose=BIG), _done("T-2", prose=BIG)])
        _write_index(root, gates=[_gate("T-1")])
        inputs = BS.collect_inputs(root)
        self.assertEqual(inputs.gated, frozenset({"T-1"}))
        selection = _shared_selection(root)
        self.assertEqual(selection.kept.get("T-1"), "gate")
        self.assertIn("T-2", selection.pruned)
        planned = scrub_board(root, AGENT, dry_run=True)
        self.assertTrue(planned.ok, planned.to_dict())
        self.assertEqual(planned["pruned"], ["T-2"])
        self.assertEqual(planned["pruned_bytes"], selection.pruned_bytes)

    def test_an_unpromoted_gate_pins_nothing(self) -> None:
        root = _project([_done("T-1", prose=BIG), _done("T-2", prose="short ")])
        _write_index(root, gates=[_gate("T-1", state="NEEDS_REVIEW")])
        self.assertEqual(BS.collect_inputs(root).gated, frozenset())
        self.assertIn("T-1", _shared_selection(root).pruned)

    def test_an_active_receipt_is_read_once_for_both_sides(self) -> None:
        root = _project([_done("T-1", prose=BIG), _done("T-2", prose="short ")])
        _write_index(root, gates=[])
        captured = intake.capture(root, "a request that produced T-1", work="T-1")
        self.assertTrue(captured["ok"], captured)
        inputs = BS.collect_inputs(root)
        self.assertEqual(inputs.receipt_works, frozenset({"T-1"}))
        self.assertEqual(_shared_selection(root).kept.get("T-1"), "receipt")

    def test_a_row_the_log_never_closed_is_kept_by_both_sides(self) -> None:
        root = _project([_done("T-1", prose=BIG), _done("T-2", prose="short ")],
                        unclosed=("T-2",))
        _write_index(root, gates=[])
        self.assertEqual(_shared_selection(root).kept.get("T-2"), "unproven")

    def test_references_are_followed_transitively_through_the_shared_path(self) -> None:
        done = [_done("T-1", extra=" | needs: T-2", prose=BIG), _done("T-2", prose="short ")]
        root = _project(
            done,
            todo=("- [ ] T-40 [P2] open work | verify: proof | needs: T-1",),
        )
        _write_index(root, gates=[])
        self.assertEqual(
            _shared_selection(root).kept, {"T-1": "reference", "T-2": "reference"}
        )


class GatePinEligibilityTests(unittest.TestCase):
    def test_a_gate_pinned_record_past_the_cap_is_not_due(self) -> None:
        # RED control: the validator's old input set (no gates) says "due".
        from saipen_engine.board import parse_board
        from saipen_engine.log import read_history_snapshot

        root = _project([_done(GATE_TICKET, prose=BIG), _done("T-1937", prose="short ")])
        _write_index(root, gates=[_gate(GATE_TICKET)])
        tickets = parse_board(_board(root).decode("utf-8"))["tickets"]
        active, works = intake.active_receipt_works(root)
        legacy_due = BS.select(tickets, read_history_snapshot(root).events, active, works)
        self.assertTrue(legacy_due.due)
        self.assertIn(GATE_TICKET, legacy_due.pruned)

        selection = _shared_selection(root)
        self.assertFalse(selection.due)
        self.assertLess(selection.pruned_bytes, BS.SCRUB_DUE_BYTES)
        self.assertEqual(selection.pruned, ("T-1937",))

    def test_the_soft_cap_still_fires_on_text_nothing_pins(self) -> None:
        root = _project([_done("T-1", prose=BIG), _done("T-2", prose=BIG)])
        _write_index(root, gates=[_gate("T-1")])
        selection = _shared_selection(root)
        self.assertTrue(selection.due)
        self.assertEqual(selection.pruned, ("T-2",))

    def test_the_clean_move_removes_only_the_unpinned_row_and_keeps_its_bytes(self) -> None:
        root = _project([_done("T-1", prose=BIG), _done("T-2", prose=BIG)])
        _write_index(root, gates=[_gate("T-1")])
        before = _board(root)
        result = scrub_board(root, AGENT)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result["pruned"], ["T-2"])
        self.assertEqual(_ids(root), ["T-1"])
        files = _evidence(root)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_bytes(), (_done("T-2", prose=BIG) + "\n").encode())
        removed = (_done("T-2", prose=BIG) + "\n").encode()
        self.assertEqual(_board(root), before.replace(removed, b""))
        self.assertEqual(_shared_selection(root).due, False)

    def test_a_second_scrub_is_idempotent_and_the_warning_state_is_unchanged(self) -> None:
        root = _project([_done("T-1", prose=BIG), _done("T-2", prose=BIG)])
        _write_index(root, gates=[_gate("T-1")])
        self.assertTrue(scrub_board(root, AGENT).ok)
        before = _board(root)
        again = scrub_board(root, AGENT)
        self.assertFalse(again.ok)
        self.assertIs(again["due"], False)
        self.assertEqual(again["prunable_records"], 0)
        self.assertEqual(_ids(root), ["T-1"])
        self.assertEqual(_board(root), before)

    def test_no_promoted_gate_is_left_pointing_at_a_pruned_row(self) -> None:
        root = _project([_done("T-1", prose=BIG), _done("T-2", prose=BIG)])
        _write_index(root, gates=[_gate("T-1")])
        gated_before = BS.collect_inputs(root).gated
        result = scrub_board(root, AGENT)
        self.assertTrue(result.ok, result.to_dict())
        remaining = set(_ids(root))
        self.assertLessEqual(set(gated_before), remaining)

    def test_a_gate_naming_a_row_absent_from_the_board_changes_no_selection(self) -> None:
        root = _project([_done("T-1", prose=BIG), _done("T-2", prose=BIG)])
        _write_index(root, gates=[_gate("T-999")])
        self.assertEqual(BS.collect_inputs(root).gated, frozenset({"T-999"}))
        selection = _shared_selection(root)
        self.assertEqual(selection.pruned, ("T-1", "T-2"))


class UnknownLedgerTests(unittest.TestCase):
    """A destructive caller never reads an unprovable ledger as "no gates"."""

    def _prunable(self) -> Path:
        return _project([_done(f"T-{n}", prose=BIG) for n in range(1, 4)])

    def _assert_refused(self, root: Path) -> None:
        with self.assertRaises(BS.ScrubInputsUnknown):
            BS.collect_inputs(root)
        before = _board(root)
        result = scrub_board(root, AGENT)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "VALIDATION_FAILED")
        self.assertIn("unknown", result.message)
        self.assertEqual(_board(root), before)
        self.assertEqual(_evidence(root), [])

    def test_a_corrupt_index_refuses_the_scrub(self) -> None:
        root = self._prunable()
        (root / ".saipen" / "future").mkdir(parents=True, exist_ok=True)
        (root / BS.FUTURE_INDEX).write_text("{not json", encoding="utf-8")
        self._assert_refused(root)
        # Pre-fix control: the diagnostic reader turns an unreadable ledger
        # into "no gates", so the operation would have pruned every row.
        from saipen_engine.board import parse_board
        from saipen_engine.log import read_history_snapshot

        tickets = parse_board(_board(root).decode("utf-8"))["tickets"]
        active, works = intake.active_receipt_works(root)
        legacy = BS.select(tickets, read_history_snapshot(root).events, active, works)
        self.assertTrue(legacy.due)
        self.assertEqual(legacy.pruned, ("T-1", "T-2", "T-3"))

    def test_a_missing_index_over_a_corpus_refuses_the_scrub(self) -> None:
        root = self._prunable()
        corpus = root / "future_gate"
        corpus.mkdir()
        (corpus / "FG-9001_x.md").write_text("<!-- SAIPEN FUTURE GATE v1 -->\n", encoding="utf-8")
        self._assert_refused(root)

    def test_a_schema_drifted_index_refuses_the_scrub(self) -> None:
        root = self._prunable()
        _write_index(root, schema=1, gates=[_gate("T-1")])
        self._assert_refused(root)

    def test_a_malformed_promoted_gate_refuses_the_scrub(self) -> None:
        root = self._prunable()
        _write_index(root, gates=[{"id": GATE_ID, "state": "PROMOTED", "slices": "oops"}])
        self._assert_refused(root)

    def test_a_malformed_slice_record_refuses_the_scrub(self) -> None:
        root = self._prunable()
        _write_index(root, gates=[{"id": GATE_ID, "state": "PROMOTED", "slices": ["T-1"]}])
        self._assert_refused(root)

    def test_an_absent_index_and_absent_corpus_is_provably_empty(self) -> None:
        root = _project([_done("T-1", prose="short ")])
        self.assertEqual(BS.collect_inputs(root).gated, frozenset())


class ValidatorFindingTests(unittest.TestCase):
    def test_a_gate_pinned_record_produces_no_soft_cap_warning(self) -> None:
        root = _project([_done(GATE_TICKET, prose=BIG), _done("T-1937", prose="short ")])
        _write_index(root, gates=[_gate(GATE_TICKET)])
        found = [line for line in _findings(root) if "[board-soft-cap]" in line]
        self.assertEqual(found, [])
        # The same BOARD without the gate ledger is the debt the old warning
        # reported: removing the ledger makes the row prunable again.
        (root / BS.FUTURE_INDEX).unlink()
        found = [line for line in _findings(root) if "[board-soft-cap]" in line]
        self.assertEqual(len(found), 1, found)


if __name__ == "__main__":
    unittest.main()
