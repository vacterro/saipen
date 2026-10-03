"""T-151: one Work's edited receipt must not decide another Work's closure.

`latest_pass_reverify` scans every `RV-*.json` newest-first. Before the fix the
integrity guard returned None out of the WHOLE scan before the scan had
established that the receipt belonged to the Work being asked about, so a single
edited byte in one Work's receipt made every other Work read as unverified --
and the validator then told the operator to re-run the strict gate once per DONE
ticket to mint receipts they already held.

The retry path in the same module (`_reverify_body`) already had the right
order: skip the untrusted record, keep scanning. This file pins the read path to
that same rule, and pins the rule T-1517 actually cares about -- an edited
receipt for THIS Work must still never let an older PASS through.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from saipen_engine import debt
from saipen_engine.journal import hash_bytes
from saipen_engine.paths import (
    history_bound_here,
    project_identity,
    project_lineage_identity,
)

REVERIFY_DIR = Path(debt.REVERIFY_DIR)


def _digest(record: dict) -> str:
    body = {k: v for k, v in record.items() if k not in debt._REVERIFY_UNDIGESTED}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hash_bytes(canonical)


def _write(root: Path, receipt_id: str, record: dict, *, seal: bool = True) -> Path:
    if seal:
        record["integrity_digest"] = _digest(record)
    path = root / REVERIFY_DIR / f"{receipt_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return path


class ForeignReceiptBlastRadius(unittest.TestCase):
    def setUp(self) -> None:
        self._origin = Path.cwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        os.chdir(self.root)
        self.ruleset = debt.findings_mod.ruleset_fingerprint()
        self.lineage = project_lineage_identity(self.root)
        self.identity = None if self.lineage is not None else project_identity(self.root)

    def tearDown(self) -> None:
        os.chdir(self._origin)
        self._tmp.cleanup()

    def _receipt(self, work: str, verdict: str) -> dict:
        record = {
            "receipt_id": "RV-000000",
            "work": work,
            "verdict": verdict,
            "ruleset_fingerprint": self.ruleset,
            "project_lineage": self.lineage,
            "project_identity": self.identity,
        }
        # A digest written over the ORIGINAL bytes, so tampering with `verdict`
        # afterwards is exactly the "edited receipt" the guard exists for.
        record["integrity_digest"] = _digest(record)
        return record

    def test_an_edited_receipt_for_another_work_leaves_this_one_honoured(self) -> None:
        _write(self.root, "RV-000001", self._receipt("T-001", "PASS"))

        foreign = self._receipt("T-999", "PASS")
        foreign["verdict"] = "PASS"
        foreign["tampered"] = "edited after the digest was written"
        _write(self.root, "RV-000009", foreign, seal=False)

        found = debt.latest_pass_reverify(self.root, "T-001")
        self.assertIsNotNone(
            found,
            "an untrusted receipt belonging to a DIFFERENT Work erased this "
            "Work's intact PASS verdict (T-151)",
        )
        self.assertEqual(found.get("work"), "T-001")

    def test_the_scan_examines_this_work_receipt_not_the_foreign_one(self) -> None:
        """The mechanism, observed on the real function rather than restated.

        `_reverify_intact` is reached once per record the scan actually looks
        at, so recording its calls records how far the scan got.
        """
        _write(self.root, "RV-000001", self._receipt("T-001", "PASS"))
        foreign = self._receipt("T-999", "PASS")
        foreign["tampered"] = "edited after the digest was written"
        _write(self.root, "RV-000009", foreign, seal=False)

        examined: list[tuple[str, bool]] = []
        real = debt._reverify_intact

        def spy(record):
            verdict = real(record)
            examined.append((str(record.get("work")), verdict))
            return verdict

        debt._reverify_intact = spy
        try:
            debt.latest_pass_reverify(self.root, "T-001")
        finally:
            debt._reverify_intact = real

        self.assertEqual(
            examined,
            [("T-001", True)],
            "the scan judged another Work's receipt instead of this one's; "
            "the integrity guard ran before the Work filter (T-151)",
        )

    def test_an_edited_receipt_for_this_work_is_still_no_verdict(self) -> None:
        """T-1517 must survive the reorder: an edited verdict never lets an
        older PASS through."""
        _write(self.root, "RV-000001", self._receipt("T-001", "PASS"))
        mine = self._receipt("T-001", "PASS")
        mine["tampered"] = "edited after the digest was written"
        _write(self.root, "RV-000002", mine, seal=False)

        self.assertIsNone(
            debt.latest_pass_reverify(self.root, "T-001"),
            "a tampered receipt for THIS Work let an older PASS through; the "
            "fail-closed guarantee the fix must not weaken",
        )

    def test_a_newer_fail_for_this_work_still_hides_an_older_pass(self) -> None:
        _write(self.root, "RV-000001", self._receipt("T-001", "PASS"))
        _write(self.root, "RV-000002", self._receipt("T-001", "FAIL"))
        self.assertIsNone(debt.latest_pass_reverify(self.root, "T-001"))

    def test_a_work_with_no_receipt_is_still_unverified(self) -> None:
        self.assertIsNone(debt.latest_pass_reverify(self.root, "T-001"))

    def test_history_binding_is_still_required(self) -> None:
        """The reorder must not weaken the other filters the scan applies."""
        record = self._receipt("T-001", "PASS")
        record["project_lineage"] = "0" * 32
        record["project_identity"] = "somewhere-else"
        _write(self.root, "RV-000001", record)
        self.assertFalse(
            history_bound_here(
                record.get("project_identity"), record.get("project_lineage"), self.root
            )
        )
        self.assertIsNone(debt.latest_pass_reverify(self.root, "T-001"))


if __name__ == "__main__":
    unittest.main()
