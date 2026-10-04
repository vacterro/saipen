"""T-151/T-155: whose receipt is it, when the file can no longer be trusted?

`latest_pass_reverify` scans every `RV-*.json` newest-first. Before T-151 the
integrity guard returned None out of the WHOLE scan before the scan had
established that the receipt belonged to the Work being asked about, so a single
edited byte in one Work's receipt made every other Work read as unverified --
and the validator then told the operator to re-run the strict gate once per DONE
ticket to mint receipts they already held.

Filtering on `work` first (T-151) opened the mirror hole: the `work` field is
exactly what an editor would rewrite, so a receipt whose Work was tampered with
stops existing for the Work it was evidence against and the scan falls through
to an older PASS. Attribution has to come from somewhere the digest cannot
cover -- `journal_op_id`, written by the journal after the digest and hashed
over the Work. A corrupt receipt minted for another Work is skipped; one minted
for this Work, or one whose Work cannot be attributed at all, is refused.

The retry path in `_reverify_body` never had this problem: it keys on the
contract digest and re-mints rather than reusing.
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


def _op_id(record: dict) -> str:
    """The journal id `reverify_work` mints for exactly these fields."""
    return "reverify." + hash_bytes(
        (
            f"{record['project_lineage']}|{record['work']}|"
            f"{record['findings_digest']}|{record['verification_contract_digest']}|"
            f"{record['receipt_id']}"
        ).encode("utf-8")
    )[:12]


def _digest(record: dict) -> str:
    body = {k: v for k, v in record.items() if k not in debt._REVERIFY_UNDIGESTED}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hash_bytes(canonical)


def _write(root: Path, receipt_id: str, record: dict) -> Path:
    """Write a receipt exactly the way `reverify_work` does: digest, THEN op id."""
    record["journal_op_id"] = _op_id(record)
    record["integrity_digest"] = _digest(record)
    path = root / REVERIFY_DIR / f"{receipt_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _edit(path: Path, **fields) -> None:
    """Tamper with a receipt AFTER it was written -- the T-1517 attack."""
    record = json.loads(path.read_text(encoding="utf-8"))
    record.update(fields)
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")


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

    def _receipt(self, work: str, verdict: str, receipt_id: str = "RV-000000") -> dict:
        return {
            "receipt_id": receipt_id,
            "work": work,
            "verdict": verdict,
            "ruleset_fingerprint": self.ruleset,
            "project_lineage": self.lineage,
            "project_identity": self.identity,
            "findings_digest": f"{abs(hash(work)) % (10**32):032x}",
            "verification_contract_digest": f"{abs(hash(verdict)) % (10**16):016x}",
        }

    def test_an_edited_receipt_for_another_work_leaves_this_one_honoured(self) -> None:
        _write(self.root, "RV-000001", self._receipt("T-001", "PASS", "RV-000001"))

        path = _write(self.root, "RV-000009", self._receipt("T-999", "PASS", "RV-000009"))
        _edit(path, tampered="edited after the digest was written")

        found = debt.latest_pass_reverify(self.root, "T-001")
        self.assertIsNotNone(
            found,
            "an untrusted receipt belonging to a DIFFERENT Work erased this "
            "Work's intact PASS verdict (T-151)",
        )
        self.assertEqual(found.get("work"), "T-001")

    def test_an_edited_work_field_still_erases_the_newer_receipt(self) -> None:
        """The T-1517 hole the reorder opened, closed by attribution."""
        _write(self.root, "RV-000001", self._receipt("T-001", "PASS", "RV-000001"))
        path = _write(self.root, "RV-000002", self._receipt("T-001", "FAIL", "RV-000002"))
        _edit(path, work="T-002")  # the receipt was NOT minted for T-002

        self.assertIsNone(
            debt.latest_pass_reverify(self.root, "T-001"),
            "rewriting a receipt's Work hid the newer FAIL from the Work it "
            "was evidence against, and an older PASS came back through (T-155)",
        )

    def test_a_receipt_with_no_attributable_work_is_refused(self) -> None:
        """Fail closed when the minting authority cannot be reproduced."""
        _write(self.root, "RV-000001", self._receipt("T-001", "PASS", "RV-000001"))
        path = _write(self.root, "RV-000002", self._receipt("T-001", "PASS", "RV-000002"))
        _edit(path, work="T-002", project_lineage="0" * 32)

        self.assertIsNone(
            debt.latest_pass_reverify(self.root, "T-001"),
            "a receipt whose Work cannot be attributed was allowed to be "
            "skipped, which is the same hole with more steps (T-155)",
        )

    def test_the_scan_examines_this_work_receipt_not_the_foreign_one(self) -> None:
        """The mechanism, observed on the real function rather than restated.

        `_reverify_intact` is reached once per record the scan actually looks
        at, so recording its calls records how far the scan got.
        """
        _write(self.root, "RV-000001", self._receipt("T-001", "PASS", "RV-000001"))
        path = _write(self.root, "RV-000009", self._receipt("T-999", "PASS", "RV-000009"))
        _edit(path, tampered="edited after the digest was written")

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
            [ok for _, ok in examined],
            [False, True],
            "the scan stopped at another Work's receipt instead of reaching "
            "this Work's (T-151)",
        )
        self.assertEqual(
            [work for work, ok in examined if ok],
            ["T-001"],
            "the only receipt judged intact was not this Work's (T-151)",
        )

    def test_a_corrupt_receipt_is_attributed_by_its_journal_op_id(self) -> None:
        record = self._receipt("T-999", "PASS", "RV-000009")
        record["journal_op_id"] = _op_id(record)
        self.assertEqual(debt._reverify_minted_work(record), "T-999")

        record["work"] = "T-001"
        self.assertIsNone(
            debt._reverify_minted_work(record),
            "a rewritten Work must not be able to reproduce the op id it was "
            "minted under",
        )

    def test_an_edited_receipt_for_this_work_is_still_no_verdict(self) -> None:
        """T-1517 must survive both reorders: an edited verdict never lets an
        older PASS through."""
        _write(self.root, "RV-000001", self._receipt("T-001", "PASS", "RV-000001"))
        path = _write(self.root, "RV-000002", self._receipt("T-001", "PASS", "RV-000002"))
        _edit(path, tampered="edited after the digest was written")

        self.assertIsNone(
            debt.latest_pass_reverify(self.root, "T-001"),
            "a tampered receipt for THIS Work let an older PASS through; the "
            "fail-closed guarantee the fix must not weaken",
        )

    def test_a_newer_fail_for_this_work_still_hides_an_older_pass(self) -> None:
        _write(self.root, "RV-000001", self._receipt("T-001", "PASS", "RV-000001"))
        _write(self.root, "RV-000002", self._receipt("T-001", "FAIL", "RV-000002"))
        self.assertIsNone(debt.latest_pass_reverify(self.root, "T-001"))

    def test_a_work_with_no_receipt_is_still_unverified(self) -> None:
        self.assertIsNone(debt.latest_pass_reverify(self.root, "T-001"))

    def test_history_binding_is_still_required(self) -> None:
        """The reorders must not weaken the other filters the scan applies."""
        record = self._receipt("T-001", "PASS", "RV-000001")
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