"""T-1443: a pytest --basetemp tree is disposable, and must never be collected
as durable evidence.

THE DEFECT, measured on FastPrompter at HEAD e1f0cad (2026-10-30). A compact
AUDAPACK export reported:

    saipen_snapshot.status                  PROTOCOL_INCOMPLETE
    saipen_snapshot.evidence_files_collected     6701
    saipen_snapshot.evidence_files_in_archive    6540
    saipen_snapshot.truncated_required_dirs      ['.saipen/evidence']

6540 + 161 = 6701, and the live tree held 25,453 files under `.saipen/evidence`
against a CONDITIONAL_DIRS cap of 4000. Of the 161 uncollected required paths,
125 were pytest `--basetemp` fixtures and 36 were durable receipts. The walk
spent its entire budget on the fixtures and stopped before the receipts, so an
export that claimed `source_review_ready: true` shipped without the evidence
behind its own acceptance claims.

`TRANSIENT_SEGMENTS` already described exactly this class of path -- "a new
transient directory appearing under an otherwise durable root is excluded the
day it appears" -- but `basetemp` was not in it. Adding it is the same
structural rule the neighbouring entries use, not a new mechanism.

These controls pin the classification in both directions: the disposable tree
is excluded, and no durable family is caught by accident. The negative half
matters more, because over-excluding turns off evidence collection silently.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import audit_manifest  # noqa: E402


class BasetempIsTransient(unittest.TestCase):
    """The measured class is excluded at any depth."""

    def test_a_basetemp_fixture_is_transient(self):
        self.assertTrue(audit_manifest.is_transient(
            "evidence/t1450_fullsuite/basetemp/test_x0/cue.wav"))

    def test_a_basetemp_segment_at_the_root_of_evidence_is_transient(self):
        self.assertTrue(audit_manifest.is_transient("evidence/basetemp/a.wav"))

    def test_a_deeper_basetemp_segment_is_transient(self):
        """The rule is nesting-independent: the segment matches at any depth."""
        self.assertTrue(audit_manifest.is_transient(
            "evidence/a/b/c/basetemp/deep/fixture.png"))

    def test_basetemp_is_in_the_declared_segment_list(self):
        """The manifest publishes its own exclusion list; the class must be in
        it, or a consumer cannot explain the omission."""
        self.assertIn("basetemp", audit_manifest.TRANSIENT_SEGMENTS)


class DurableFamiliesSurvive(unittest.TestCase):
    """The families the 36 real omissions belonged to are NOT excluded."""

    def test_durable_t1442_pair_logs_are_not_transient(self):
        for rel in ("evidence/t1442/pair/half-FAIL-prefix.log",
                    "evidence/t1442/pair/half-PASS-postfix.log",
                    "evidence/t1442/verify_records.log"):
            with self.subTest(rel=rel):
                self.assertFalse(audit_manifest.is_transient(rel))

    def test_acceptance_capture_images_are_not_transient(self):
        for rel in ("evidence/t1441/captures/hover_12_compact.png",
                    "evidence/t1441/captures/gauge_08_accounts_4x.png",
                    "evidence/t1441/measure_hover.py"):
            with self.subTest(rel=rel):
                self.assertFalse(audit_manifest.is_transient(rel))

    def test_loose_evidence_files_are_not_transient(self):
        for rel in ("evidence/t1223-checkbox-golden-default.png",
                    "evidence/t1450_fullsuite/run_output.log"):
            with self.subTest(rel=rel):
                self.assertFalse(audit_manifest.is_transient(rel))

    def test_externalized_log_detail_is_not_transient(self):
        """T-1374: a LOG `detail_ref` that resolves to nothing is a dangling
        pointer, so this family must stay collectable."""
        self.assertFalse(audit_manifest.is_transient(
            "recovery/log-detail/E-4591-abcdef0123456789.json"))

    def test_a_name_merely_containing_basetemp_is_not_transient(self):
        """Only a whole SEGMENT matches. A file called `basetemp_notes.md` is a
        durable note, and excluding it would be a silent evidence loss."""
        self.assertFalse(audit_manifest.is_transient(
            "evidence/t1443/basetemp_notes.md"))

    def test_a_staging_family_is_still_transient(self):
        """The pre-existing classes must keep working."""
        self.assertTrue(audit_manifest.is_transient("evidence/.staging/a.bin"))
        self.assertTrue(audit_manifest.is_transient("evidence/__pycache__/m.pyc"))


if __name__ == "__main__":
    unittest.main()
