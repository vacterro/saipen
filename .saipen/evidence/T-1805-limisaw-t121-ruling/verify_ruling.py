"""Executable verification and deliberate red controls for T-1805 (SRC-264)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SAIPEN_ROOT = Path(__file__).resolve().parents[3]
LIMISAW_ROOT = Path(r"V:\___VAC\__K\__CODE\_PY\_LIMISAW")
RULING_PATH = Path(__file__).resolve().with_name("RULING.md")

if str(SAIPEN_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(SAIPEN_ROOT / "tools"))

from saipen_engine import operator_task, oracle  # noqa: E402


class T1805LimisawRulingVerification(unittest.TestCase):
    """Verify SRC-264 R001..R005 invariants and deliberate negative controls."""

    def test_phase0_authority_and_limisaw_non_mutation(self) -> None:
        self.assertTrue((SAIPEN_ROOT / "saipen" / "phases" / "verify.md").is_file())
        verify_md = (SAIPEN_ROOT / "saipen" / "phases" / "verify.md").read_text(encoding="utf-8")
        self.assertIn("<!-- RULE-OWNER: VERIFY-ORACLE-01 -->", verify_md)
        self.assertEqual(oracle.RULE_ID, "VERIFY-ORACLE-01")

        # LIMISAW state remains BUILD / T-121 and SRC-044 is model_supplied
        state_text = (LIMISAW_ROOT / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn("phase: BUILD", state_text)
        self.assertIn("task: T-121", state_text)

    def test_phase1_and_phase2_comparative_oracle_admissibility_and_red_controls(self) -> None:
        recovery_dir = LIMISAW_ROOT / ".saipen" / "evidence" / "T-121-pre-fix-recovery"
        sums_text = (recovery_dir / "SHA256SUMS").read_text(encoding="utf-8")
        digests: dict[str, str] = {}
        for line in sums_text.splitlines():
            line = line.strip()
            if not line:
                continue
            sha, rel = line.split(" *", 1)
            digests[rel] = sha

        # Oracle equivalence across root, pre-v0.0.11, and current-subject
        oracle_sha = digests["./revocation_oracle.cs"]
        self.assertEqual(oracle_sha, "d1517509f4b53c06bccfc4583d0528148d9e28311ce92b2d2e7c9702a658293b")
        self.assertEqual(digests["./pre-v0.0.11/revocation_oracle.cs"], oracle_sha)
        self.assertEqual(digests["./current-subject/revocation_oracle.cs"], oracle_sha)

        # Subject provenance differs between v0.0.11 and current-subject
        pre_subject = digests["./pre-v0.0.11/LIMISAW.cs"]
        post_subject = digests["./current-subject/LIMISAW.cs"]
        self.assertNotEqual(pre_subject, post_subject)

        # Pre-fix exit is 1 (4/38 FAIL) and post-fix exit is 0 (38/38 PASS)
        self.assertEqual((recovery_dir / "pre-v0.0.11" / "compile.exit").read_text(encoding="ascii").strip(), "0")
        self.assertEqual((recovery_dir / "current-subject" / "compile.exit").read_text(encoding="ascii").strip(), "0")
        self.assertEqual((recovery_dir / "pre-v0.0.11" / "run.exit").read_text(encoding="ascii").strip(), "1")
        self.assertEqual((recovery_dir / "current-subject" / "run.exit").read_text(encoding="ascii").strip(), "0")
        self.assertIn("FAIL 38 checks; failures=4", (recovery_dir / "pre-v0.0.11" / "run.log").read_text(encoding="utf-8"))
        self.assertIn("PASS 38 checks; failures=0", (recovery_dir / "current-subject" / "run.log").read_text(encoding="utf-8"))

        # Anchored VERIFY-ORACLE-01 records are ADMISSIBLE
        fail_line = (
            f"REGRESSION-EVIDENCE FAIL verifier:{oracle_sha} subject:{pre_subject} "
            "-- pre-v0.0.11 4/38 FAIL"
        )
        pass_line = (
            f"REGRESSION-EVIDENCE PASS verifier:{oracle_sha} subject:{post_subject} "
            "-- current-subject 38/38 PASS"
        )
        rec_fail = oracle.parse_evidence(fail_line)
        rec_pass = oracle.parse_evidence(pass_line)
        self.assertIsNotNone(rec_fail)
        self.assertIsNotNone(rec_pass)
        verdict = oracle.regression_evidence_verdict([rec_fail, rec_pass])
        self.assertEqual(verdict["code"], oracle.ADMISSIBLE)
        self.assertTrue(verdict["admissible"])

        # Deliberate red controls for VERIFY-ORACLE-01
        mutated_pass = dict(rec_pass, verifier="0" * 64)
        self.assertEqual(
            oracle.regression_pair_verdict(rec_fail, mutated_pass)["code"],
            oracle.ORACLE_CHANGED,
        )
        unchanged_subject_pass = dict(rec_pass, subject=pre_subject)
        self.assertEqual(
            oracle.regression_pair_verdict(rec_fail, unchanged_subject_pass)["code"],
            oracle.SUBJECT_UNCHANGED,
        )
        self.assertEqual(
            oracle.regression_evidence_verdict([rec_pass])["code"],
            oracle.NO_EVIDENCE,
        )

    def test_phase3_provenance_cannot_promote_model_supplied(self) -> None:
        expected_pairs = {
            "SRC-043": "T-133",
            "SRC-044": "T-134",
            "SRC-045": "T-135",
        }
        for receipt_id, work_id in expected_pairs.items():
            meta_path = LIMISAW_ROOT / ".saipen" / "intake" / "active" / f"{receipt_id}.meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(meta["linked_work"], work_id)
            prov = meta["request_provenance"]
            self.assertEqual(prov["witness"], "model_supplied")
            auth = operator_task.authority_for_provenance(prov)
            self.assertFalse(auth["user_explicit"])
            self.assertFalse(auth["preempt_active_work"])
            self.assertFalse(auth["goal_pivot"])
            self.assertFalse(auth["reset_bounded_authority"])
            self.assertEqual(operator_task.projection_priority("P1", auth), "P2")

            # Retroactive promotion check via authority_for_receipt
            receipt_auth = operator_task.authority_for_receipt(LIMISAW_ROOT, receipt_id)
            self.assertEqual(receipt_auth["witness"], "model_supplied")
            self.assertFalse(receipt_auth["user_explicit"])

        # Positive control: valid operator_carrier provenance grants user_explicit
        carrier_auth = operator_task.authority_for_provenance(
            {
                "witness": "operator_carrier",
                "compared_digest": "a" * 64,
                "declared_by": "SAIPEN_TASK_SHA256",
            }
        )
        self.assertTrue(carrier_auth["user_explicit"])
        self.assertTrue(carrier_auth["preempt_active_work"])
        self.assertEqual(operator_task.projection_priority("P1", carrier_auth), "P1")

    def test_phase4_ruling_report_completeness(self) -> None:
        text = RULING_PATH.read_text(encoding="utf-8")
        for required_section in (
            "STATUS",
            "AUTHORITY",
            "VERIFY-ORACLE-01 RULING",
            "EVIDENCE ADMISSIBILITY",
            "PROVENANCE FINDINGS",
            "PROTOCOL CHANGES, IF AUTHORIZED",
            "NEXT EXACT ACTION",
            "NEED USER",
        ):
            self.assertIn(required_section, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
