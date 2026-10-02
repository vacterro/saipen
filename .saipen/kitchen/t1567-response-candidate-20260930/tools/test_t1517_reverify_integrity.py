"""T-1517: an RV receipt is evidence only while its bytes match its digest.

`latest_pass_reverify` -- the validator's closure-evidence path -- read the
receipt JSON and trusted its verdict, so editing a FAIL receipt to PASS made a
DONE Work closure-proven. The digest was never checkable: `reverify_work`
computes it before the journal adds `journal_op_id`, and `load_reverify_receipt`
included that field, rejecting every journaled receipt (0 of 444 receipts found
on this machine passed it). The reuse scan in `reverify_work` also handed a
tampered receipt back as REVERIFY_REUSED, so re-running the cure never minted a
fresh one.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import debt as debt_mod  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_reverify import ReverifyFixture  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class ReverifyIntegrityTests(ReverifyFixture):
    def reverify(self, *, passing: bool) -> dict:
        problems = [] if passing else [self._own_problem()]
        with patch.object(debt_mod, "capture_findings", return_value=self._canned(problems)):
            result = debt_mod.reverify_work(
                self.root, "T-001", "probe", runs=["exit 0" if passing else "exit 1"]
            )
        self.assertTrue(result["ok"], result)
        return result

    def edit(self, receipt_id: str, **fields) -> None:
        path = self._receipt_dir() / f"{receipt_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(fields)
        path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

    def test_a_journaled_receipt_verifies_in_place_and_in_a_copy(self):
        receipt_id = self.reverify(passing=True)["receipt_id"]
        self.assertEqual(
            debt_mod.load_reverify_receipt(self.root, receipt_id)["receipt_id"], receipt_id
        )
        base = Path(tempfile.mkdtemp(prefix="saipen-t1517-copy-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        moved = base / "moved" / "project"
        shutil.copytree(self.root, moved)
        self.assertEqual(
            debt_mod.load_reverify_receipt(moved, receipt_id)["receipt_id"], receipt_id
        )
        self.assertEqual(debt_mod.current_tree_reverify(moved, "T-001")["receipt_id"], receipt_id)

    def test_a_fail_edited_to_pass_is_not_closure_evidence(self):
        failed = self.reverify(passing=False)
        self.assertEqual(failed["verdict"], "FAIL")
        self.assertIsNone(debt_mod.current_tree_reverify(self.root, "T-001"))
        self.edit(failed["receipt_id"], verdict="PASS")
        self.assertIsNone(debt_mod.current_tree_reverify(self.root, "T-001"))
        with self.assertRaises(debt_mod.DebtRefusal) as caught:
            debt_mod.load_reverify_receipt(self.root, failed["receipt_id"])
        self.assertEqual(caught.exception.code, "REVERIFY_RECEIPT_CORRUPT")

    def test_an_edited_newest_receipt_never_lets_an_older_pass_through(self):
        passed = self.reverify(passing=True)["receipt_id"]
        failed = self.reverify(passing=False)["receipt_id"]
        self.assertNotEqual(passed, failed)
        self.edit(failed, verdict="PASS")
        self.assertIsNone(debt_mod.latest_pass_reverify(self.root, "T-001"))

    def test_an_edited_work_field_never_lets_an_older_pass_through(self):
        passed = self.reverify(passing=True)["receipt_id"]
        failed = self.reverify(passing=False)["receipt_id"]
        self.assertNotEqual(passed, failed)
        self.edit(failed, work="T-002")
        self.assertIsNone(debt_mod.latest_pass_reverify(self.root, "T-001"))

    def test_rerunning_reverify_mints_the_cure_after_an_edit(self):
        first = self.reverify(passing=True)["receipt_id"]
        self.edit(first, agent="someone-else")
        self.assertIsNone(debt_mod.current_tree_reverify(self.root, "T-001"))
        again = self.reverify(passing=True)
        self.assertNotEqual(again.get("code"), "REVERIFY_REUSED", again)
        self.assertNotEqual(again["receipt_id"], first)
        self.assertEqual(
            debt_mod.current_tree_reverify(self.root, "T-001")["receipt_id"], again["receipt_id"]
        )

    def test_a_repeated_fail_is_recorded_again(self):
        first = self.reverify(passing=False)["receipt_id"]
        second = self.reverify(passing=False)
        self.assertEqual(second["verdict"], "FAIL")
        self.assertNotEqual(second["receipt_id"], first)

    def test_an_intact_pass_is_still_reused(self):
        first = self.reverify(passing=True)["receipt_id"]
        again = self.reverify(passing=True)
        self.assertEqual(again.get("code"), "REVERIFY_REUSED", again)
        self.assertEqual(again["receipt_id"], first)


if __name__ == "__main__":
    unittest.main()
