"""T-1937: a promoted future-gate slice must be closable, and only from truth.

The measured defect: `record_slice` is called only by `saipen future promote`
and with the default `closure="open"`. Nothing advanced a slice when its ticket
reached `## DONE`, and `saipen future refresh` only re-hashed documents. So
`readiness()` answered INELIGIBLE for ever on
`f"{len(gate.open_slices)} slice(s) still open on a promoted gate"`
(`future_gate.py:996`) and a finished gate could never close.

Measured on FG-0046/T-1936: T-1936 was `[x]` under `## DONE` while the index
still read `closure: "open"`.

These tests pin the repair and, just as importantly, its REFUSALS -- a closure
writer that accepts an argument would be the same class of defect as a
hand-edited index:

* a slice whose ticket is DONE closes as `done`;
* a superseded ticket closes as `superseded`;
* a slice whose ticket is still TODO stays `open`;
* a ticket merely ABSENT from BOARD does not close anything;
* the function exposes no way to pass a closure in.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from saipen_engine import future_gate

BOARD = """# BOARD

## TODO
- [ ] T-2 [P2] still open | verify: it is

## DOING

## BLOCKED

## DONE
- [x] T-1 [P2] finished work | verify: it was | closure_mode: own_patch
- [x] T-3 [P2] replaced work | verify: it was | closure_mode: superseded_verified
"""


def _tickets(text: str) -> dict:
    from saipen_engine.board import parse_board

    board = parse_board(text)
    assert not board["errors"], board["errors"]
    return board["tickets"]


class SliceClosureTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        (self.root / ".saipen" / "future").mkdir(parents=True)
        (self.root / "future_gate").mkdir()
        (self.root / ".saipen" / "BOARD.md").write_text(BOARD, encoding="utf-8")

    def _index(self, slices: list[dict]) -> None:
        # Written through the module's own writer, not by hand: a fixture that
        # builds its own JSON silently stops testing the real index contract the
        # moment that contract grows a field (it did here -- the `marker`).
        # The gate DOCUMENT is real too. Without it, `build_index` takes the
        # "document vanished" path that copies the whole prior gate dict, so a
        # refresh test would pass through a path that never touches the entry
        # builder -- measured: two slice mutations left the test green because
        # the absent-document copy preserved the closure either way.
        path = self.root / "future_gate" / "FG-9001_fixture.md"
        path.write_text(
            "<!-- SAIPEN FUTURE GATE v1 -->\n"
            "id: FG-9001\n"
            "title: fixture gate\n"
            "state: PROMOTED\n"
            "priority: P2\n"
            "basis: measured\n"
            "estimate: 1\n"
            "slice: one bounded fixture slice\n"
            "needs: none\n"
            "evidence: T-1\n",
            encoding="utf-8",
        )
        index = {
            "marker": future_gate.INDEX_MARKER,
            "schema": future_gate.SCHEMA_VERSION,
            "corpus": {"schema": future_gate.SCHEMA_VERSION, "documents": 0,
                       "unreadable": 0, "fingerprint": "0" * 64},
            "gates": [
                {
                    "id": "FG-9001",
                    "path": "future_gate/FG-9001_fixture.md",
                    "title": "fixture gate",
                    "state": future_gate.PROMOTED,
                    "machine_readable": True,
                    "present": True,
                    "slices": slices,
                }
            ],
        }
        future_gate.write_index(self.root, index)

    def _closures(self) -> list[str]:
        data = json.loads(
            (self.root / ".saipen" / "future" / "index.json").read_text(encoding="utf-8")
        )
        return [s.get("closure") for s in data["gates"][0]["slices"]]

    def test_a_done_ticket_closes_its_slice(self):
        self._index([{"ticket": "T-1", "closure": "open", "slice": "s", "digest": "d"}])
        outcome = future_gate.reconcile_slice_closures(self.root, _tickets(BOARD))
        self.assertTrue(outcome["ok"], outcome)
        self.assertEqual(outcome["changes"],
                         [{"gate": "FG-9001", "ticket": "T-1", "closure": "done"}])
        self.assertEqual(self._closures(), ["done"])

    def test_a_superseded_ticket_closes_as_superseded(self):
        self._index([{"ticket": "T-3", "closure": "open", "slice": "s", "digest": "d"}])
        future_gate.reconcile_slice_closures(self.root, _tickets(BOARD))
        self.assertEqual(self._closures(), ["superseded"])

    def test_a_todo_ticket_stays_open(self):
        self._index([{"ticket": "T-2", "closure": "open", "slice": "s", "digest": "d"}])
        outcome = future_gate.reconcile_slice_closures(self.root, _tickets(BOARD))
        self.assertEqual(outcome["changes"], [])
        self.assertEqual(outcome["mutation"], "none")
        self.assertEqual(self._closures(), ["open"])

    def test_a_ticket_absent_from_board_does_not_close_anything(self):
        """Absence is not DONE: a truncated or corrupt parse must not ship work."""
        self._index([{"ticket": "T-999", "closure": "open", "slice": "s", "digest": "d"}])
        outcome = future_gate.reconcile_slice_closures(self.root, _tickets(BOARD))
        self.assertEqual(outcome["changes"], [])
        self.assertEqual(self._closures(), ["open"])

    def test_an_already_closed_slice_is_not_rewritten(self):
        self._index([{"ticket": "T-1", "closure": "done", "slice": "s", "digest": "d"}])
        outcome = future_gate.reconcile_slice_closures(self.root, _tickets(BOARD))
        self.assertEqual(outcome["changes"], [])
        self.assertEqual(self._closures(), ["done"])

    def test_the_verb_takes_no_caller_supplied_closure(self):
        """The closure must be derived. A `closure=` parameter would be the hole."""
        import inspect

        params = inspect.signature(future_gate.reconcile_slice_closures).parameters
        self.assertNotIn("closure", params)
        self.assertNotIn("state", params)
        self.assertNotIn("resolved", params)

    def test_a_tree_without_board_still_refreshes(self):
        """Found by a neighbour suite, not by this one: `refresh` is the
        projection builder and must run on a corpus-only fixture. Wiring the
        derivation into it made an absent BOARD.md an exception, which broke
        every caller that builds an index from documents alone."""
        (self.root / ".saipen" / "BOARD.md").unlink()
        self._index([{"ticket": "T-1", "closure": "open", "slice": "s", "digest": "d"}])
        future_gate.refresh(self.root)
        self.assertEqual(
            self._closures(), ["open"],
            "an absent BOARD proves nothing DONE, so nothing may close",
        )

    def test_a_rebuild_does_not_reopen_a_derived_closure(self):
        """Found by the REVIEW self-audit. `build_index` takes each gate's
        slices from the PRIOR index, so a reconcile that ran before the rebuild
        survives it -- and a rebuild that dropped the closure would silently
        undo the derivation on the very next refresh."""
        self._index([{"ticket": "T-1", "closure": "open", "slice": "s", "digest": "d"}])
        future_gate.reconcile_slice_closures(self.root, _tickets(BOARD))
        self.assertEqual(self._closures(), ["done"])
        future_gate.refresh(self.root)
        self.assertEqual(
            self._closures(), ["done"],
            "the rebuild reopened a slice the derivation had resolved",
        )


class GateBecomesRoutableTests(unittest.TestCase):
    """The consequence: a closed gate is no longer INELIGIBLE for ever."""

    def test_readiness_stops_reporting_open_slices(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        root = Path(scratch.name)
        (root / ".saipen" / "future").mkdir(parents=True)
        (root / ".saipen" / "BOARD.md").write_text(BOARD, encoding="utf-8")
        index = {
            "marker": future_gate.INDEX_MARKER,
            "schema": future_gate.SCHEMA_VERSION,
            "corpus": {"schema": future_gate.SCHEMA_VERSION, "documents": 0,
                       "unreadable": 0, "fingerprint": "0" * 64},
            "gates": [
                {"id": "FG-9002", "path": "p", "title": "t", "state": future_gate.PROMOTED,
                 "machine_readable": True, "present": True, "slice": "a bounded slice",
                 "evidence": ["T-1"],
                 "slices": [{"ticket": "T-1", "closure": "open", "slice": "s", "digest": "d"}]}
            ],
        }
        future_gate.write_index(root, index)
        gate = future_gate.get_gate(root, "FG-9002")
        self.assertEqual(len(gate.open_slices), 1, "the fixture slice must start open")
        self.assertFalse(gate.closed, "a gate with an open slice is not closed")
        before, before_reasons = future_gate.readiness(gate, root, _tickets(BOARD))
        # Readiness short-circuits on `state PROMOTED is terminal` before it can
        # ever reach the open-slice branch, so the interesting assertion is not
        # the verdict but the two structural facts above: the slice is open and
        # the gate is not closed. Both must flip after the derivation.
        self.assertEqual(before, future_gate.INELIGIBLE)

        future_gate.reconcile_slice_closures(root, _tickets(BOARD))

        gate = future_gate.get_gate(root, "FG-9002")
        self.assertEqual(gate.open_slices, [], "the derivation left the slice open")
        self.assertTrue(gate.closed, "a gate with every slice resolved must read closed")
        after, after_reasons = future_gate.readiness(gate, root, _tickets(BOARD))
        self.assertFalse(
            any("still open" in reason for reason in after_reasons),
            f"the closed slice is still reported open: {after_reasons}",
        )


if __name__ == "__main__":
    unittest.main()
