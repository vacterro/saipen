"""T-1938: a disproven finding must not be recorded as implemented work.

`reconcile_slice_closures` (T-1937) derives a slice closure from BOARD truth.
Its first version mapped `superseded_verified` to `superseded` and EVERY other
DONE ticket to `done`. That is wrong for `finding_invalidated`, whose contract
in `operations.py` is `implementation_delta: none` plus `invalidation_evidence`:
the finding was disproven, so no code was owed and none was written.

Recording it as `done` would tell every later reader that the slice's work
exists. The vocabulary FUTURE.md section 1 already defines covers this: a slice
that will not be implemented closes as `rejected`.

Measured scope: BOARD carries five `finding_invalidated` tickets (T-1625,
T-1639, T-1699, T-1824, T-1869) and none is bound to a gate slice, so the wrong
answer was latent rather than live.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from saipen_engine import future_gate

BOARD = """# BOARD

## TODO
- [ ] T-5 [P2] open work | verify: it is

## DOING

## BLOCKED

## DONE
- [x] T-1 [P2] implemented | verify: it was | closure_mode: own_patch
- [x] T-2 [P2] invented | verify: nothing was owed | closure_mode: finding_invalidated | implementation_delta: none
- [x] T-3 [P2] replaced | verify: it was | closure_mode: superseded_verified
- [x] T-4 [P2] inherited proof | verify: it was | closure_mode: inherited_verified
"""


def _tickets(text: str) -> dict:
    from saipen_engine.board import parse_board

    board = parse_board(text)
    assert not board["errors"], board["errors"]
    return board["tickets"]


class InvalidatedFindingTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        (self.root / ".saipen" / "future").mkdir(parents=True)
        (self.root / "future_gate").mkdir()
        (self.root / ".saipen" / "BOARD.md").write_text(BOARD, encoding="utf-8")

    def _index(self, ticket: str) -> None:
        # A real gate document: without it `build_index` takes the
        # "document vanished" path and copies the prior gate dict whole, which
        # hides every slice mutation (measured, T-1937).
        (self.root / "future_gate" / "FG-9002_fixture.md").write_text(
            "<!-- SAIPEN FUTURE GATE v1 -->\n"
            "id: FG-9002\n"
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
        future_gate.write_index(
            self.root,
            {
                "marker": future_gate.INDEX_MARKER,
                "schema": future_gate.SCHEMA_VERSION,
                "corpus": {"schema": future_gate.SCHEMA_VERSION, "documents": 0,
                           "unreadable": 0, "fingerprint": "0" * 64},
                "gates": [
                    {
                        "id": "FG-9002",
                        "path": "future_gate/FG-9002_fixture.md",
                        "title": "fixture gate",
                        "state": future_gate.PROMOTED,
                        "machine_readable": True,
                        "present": True,
                        "slices": [
                            {"ticket": ticket, "closure": "open", "slice": "s", "digest": "d"}
                        ],
                    }
                ],
            },
        )

    def _closure(self) -> str:
        data = json.loads(
            (self.root / ".saipen" / "future" / "index.json").read_text(encoding="utf-8")
        )
        return data["gates"][0]["slices"][0]["closure"]

    def test_an_invalidated_finding_closes_as_rejected(self):
        self._index("T-2")
        outcome = future_gate.reconcile_slice_closures(self.root, _tickets(BOARD))
        self.assertEqual(
            self._closure(), "rejected",
            "a disproven finding (implementation_delta: none) must never read as done",
        )
        self.assertEqual(
            outcome["changes"], [{"gate": "FG-9002", "ticket": "T-2", "closure": "rejected"}]
        )

    def test_an_implemented_ticket_still_closes_as_done(self):
        """The control that keeps the fix from over-reaching: only the
        invalidation mode changes. own_patch and inherited_verified really were
        implemented, so their slices are `done`."""
        for ticket in ("T-1", "T-4"):
            with self.subTest(ticket=ticket):
                self._index(ticket)
                future_gate.reconcile_slice_closures(self.root, _tickets(BOARD))
                self.assertEqual(self._closure(), "done")

    def test_a_superseded_ticket_is_still_superseded(self):
        self._index("T-3")
        future_gate.reconcile_slice_closures(self.root, _tickets(BOARD))
        self.assertEqual(self._closure(), "superseded")

    def test_every_resolved_vocabulary_is_one_the_gate_accepts(self):
        """`rejected` must be a closure `open_slices` recognises as resolved --
        a value the dataclass counted as open would close nothing."""
        for ticket in ("T-1", "T-2", "T-3", "T-4"):
            with self.subTest(ticket=ticket):
                self._index(ticket)
                future_gate.reconcile_slice_closures(self.root, _tickets(BOARD))
                gate = future_gate.get_gate(self.root, "FG-9002")
                self.assertEqual(gate.open_slices, [])
                self.assertTrue(gate.closed)
                self.assertIn(self._closure(), future_gate.CLOSURES)


if __name__ == "__main__":
    unittest.main()
