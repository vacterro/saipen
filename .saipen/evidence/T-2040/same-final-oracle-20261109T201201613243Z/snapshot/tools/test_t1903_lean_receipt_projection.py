"""The routing projection stops paying for fields it discards (T-1903).

`queued_source_projection` walks every active Source receipt to find the oldest
unprojected explicit user request. It reads exactly one field per receipt --
`receipt` -- and then re-reads that candidate's metadata itself for
`linked_work` and `source_kind`. The projection it walked was the FULL
`active_receipts`, which for each of the 195 active receipts also computed a
coverage summary (0.122 s total) and a distribution projection (0.203 s total).
Both were discarded on every routing pass.

`active_receipts(root, coverage=False)` returns identity and membership only.
The risk this file guards is not speed, it is equivalence: a cheaper projection
must not change WHICH receipts are routed, in WHAT order, or whether an
unreadable receipt still refuses the pass.

Four things could silently go wrong, so each has its own case:

1. **Order.** The full projection sorts receipt ids; so must the lean one. A
   queue that routes the newest request instead of the oldest is a different
   queue.
2. **Membership.** `work=` filtering must still apply, because a caller that
   narrows to one Work must not suddenly see every receipt.
3. **Fields.** The lean form must carry `receipt`, `source_sha256` and
   `linked_work`, and must NOT pretend to carry the coverage fields -- a caller
   reading `item["requirements"]` from it should get a KeyError, not a silent
   zero that reads as "no requirements".
4. **The default.** `coverage=True` is the existing contract. Every other
   caller (context, readiness, source_append) keeps it, so their dicts must be
   unchanged down to the key set.

No assertion anywhere in this file measures a duration. The measured numbers
live in the ticket evidence; a timing assertion on a shared machine is a flaky
test, and this project has been bitten by that before.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import saipen_engine.intake as intake  # noqa: E402


class ActiveReceiptsProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1903-")
        self.root = Path(self._tmp.name)
        self.memory = self.root / ".saipen"
        self.memory.mkdir(parents=True)
        for name in ("STATE.md", "BOARD.md", "LOG.md"):
            (self.memory / name).write_text("", encoding="utf-8")
        self._active = self.memory / "intake" / "active"
        self._active.mkdir(parents=True)
        self._coverage = self.memory / "intake" / "coverage"
        self._coverage.mkdir(parents=True)
        (self.memory / "intake" / "contracts").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _add(self, receipt: str, sha: str, linked: str | None, kind: str = "user_instruction"):
        import json

        (self._active / f"{receipt}.md").write_text(f"body {receipt}\n", encoding="utf-8")
        meta = {
            "schema_version": 1,
            "receipt": receipt,
            "source_sha256": sha,
            "source_kind": kind,
        }
        if linked:
            meta["linked_work"] = linked
        (self._active / f"{receipt}.meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )
        (self._coverage / f"{receipt}.json").write_text(
            json.dumps({"requirements": {}}), encoding="utf-8"
        )

    def _index(self, receipts: list[tuple[str, str]]):
        import json

        payload = {
            "schema_version": 1,
            "next_id": 4,
            "active": {rid: {"source_sha256": sha} for rid, sha in receipts},
            "archive": {},
            "tombstones": {},
        }
        (self.memory / "intake" / "index.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_lean_matches_full_on_order_and_membership(self):
        rows = [("SRC-003", "c" * 64), ("SRC-001", "a" * 64), ("SRC-002", "b" * 64)]
        for rid, sha in rows:
            self._add(rid, sha, None)
        self._index(rows)
        full = intake.active_receipts(self.root)
        lean = intake.active_receipts(self.root, coverage=False)
        self.assertEqual([x["receipt"] for x in full], [x["receipt"] for x in lean])
        self.assertEqual(
            [x["receipt"] for x in lean], ["SRC-001", "SRC-002", "SRC-003"]
        )
        self.assertEqual(
            [x["linked_work"] for x in full], [x["linked_work"] for x in lean]
        )
        self.assertEqual(
            [x["source_sha256"] for x in full], [x["source_sha256"] for x in lean]
        )

    def test_lean_keeps_the_work_filter(self):
        self._add("SRC-001", "a" * 64, "T-001")
        self._add("SRC-002", "b" * 64, "T-002")
        self._add("SRC-003", "c" * 64, None)
        self._index([("SRC-001", "a" * 64), ("SRC-002", "b" * 64), ("SRC-003", "c" * 64)])
        narrowed = intake.active_receipts(self.root, work="T-002", coverage=False)
        self.assertEqual([x["receipt"] for x in narrowed], ["SRC-002"])

    def test_lean_does_not_fabricate_coverage_fields(self):
        self._add("SRC-001", "a" * 64, None)
        self._index([("SRC-001", "a" * 64)])
        lean = intake.active_receipts(self.root, coverage=False)[0]
        self.assertEqual(
            set(lean), {"receipt", "source_sha256", "linked_work"},
            "the lean projection grew a field, so a caller may read a value that "
            "was never proven",
        )
        for absent in ("requirements", "terminal", "unresolved", "distribution"):
            self.assertNotIn(absent, lean)

    def test_full_projection_is_unchanged_by_default(self):
        self._add("SRC-001", "a" * 64, None)
        self._index([("SRC-001", "a" * 64)])
        full = intake.active_receipts(self.root)[0]
        for present in ("requirements", "terminal", "unresolved", "distribution"):
            self.assertIn(
                present, full,
                "the default projection lost a field other callers rely on",
            )

    def test_index_metadata_drift_still_refuses_in_lean_mode(self):
        """"Cheaper" must not mean "less careful": drift is refused either way."""
        self._add("SRC-001", "a" * 64, None)
        self._index([("SRC-001", "b" * 64)])
        for coverage in (True, False):
            with self.assertRaises(ValueError) as caught:
                intake.active_receipts(self.root, coverage=coverage)
            self.assertIn("index metadata drift", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
