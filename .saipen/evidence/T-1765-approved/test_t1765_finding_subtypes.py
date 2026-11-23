"""T-1765: global finding conditions and explicit v2 baseline compatibility."""

from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch

from saipen_engine import debt, findings
import test_debt_gate as debt_fixture


HANDOFF = "cross-doc drift [root-file-set] -- unexpected root files: ['T-1446', 'tuple[bool']"


def classify(message: str) -> dict:
    return findings.classify("problem", message)


class FindingSubtypeTests(unittest.TestCase):
    def test_the_handoff_retains_its_rule_subtype_and_both_filenames(self):
        row = classify(HANDOFF)
        self.assertEqual(row["rule_id"], "cross_doc_drift")
        self.assertEqual(row["subject_kind"], "global")
        self.assertIsNone(row["subject_id"])
        self.assertIn("root-file-set", row["detail"])
        self.assertIn("T-1446", row["detail"])
        self.assertIn("tuple[bool", row["detail"])

    def test_different_subtypes_with_the_same_id_are_changed_conditions(self):
        first = classify(HANDOFF)
        second = classify("cross-doc drift [release-version] -- mismatch in T-1446")
        self.assertEqual(first["finding_key"], second["finding_key"])
        self.assertNotEqual(first["detail_hash"], second["detail_hash"])
        self.assertEqual(findings.compare_finding(first, second), "CHANGED")

    def test_another_offending_filename_changes_the_condition(self):
        first = classify(HANDOFF)
        second = classify(HANDOFF.replace("tuple[bool", "tuple[str"))
        self.assertEqual(first["finding_key"], second["finding_key"])
        self.assertNotEqual(first["detail_hash"], second["detail_hash"])

    def test_captured_global_rules_keep_non_id_parts_of_the_capture(self):
        first = classify("ticket ref [T-1446 extra-a] isn't numeric")
        second = classify("ticket ref [T-1446 extra-b] isn't numeric")
        self.assertEqual(first["rule_id"], "log_ticket_ref")
        self.assertEqual(first["finding_key"], second["finding_key"])
        self.assertNotEqual(first["detail_hash"], second["detail_hash"])

    def test_volatile_line_numbers_counts_and_spacing_stay_normalized(self):
        first = classify("cross-doc drift [root-file-set] -- T-1446.py:12 has 3 lines in 2s")
        second = classify("cross-doc drift [root-file-set] --  T-1446.py:99 has 44 lines in 9s")
        self.assertEqual(first["detail_hash"], second["detail_hash"])
        self.assertEqual(findings.compare_finding(first, second), "CARRIED")

    def test_credential_redaction_precedes_global_subtype_preservation(self):
        secret = "sk-live-T-1446-DO-NOT-SERIALIZE"
        row = classify(f"SOURCE_CREDENTIALS_UNSAFE SRC-33 {secret}; {HANDOFF}")
        self.assertTrue(row["credential"])
        self.assertIsNone(row["detail"])
        self.assertNotIn(secret, json.dumps(row))
        self.assertNotIn("root-file-set", json.dumps(row))

    def test_subject_scoped_id_normalization_stays_stable(self):
        first = classify("ticket T-1446 has no ticket-bearing closure event at file.py:12")
        second = classify("ticket T-1446 has no ticket-bearing closure event at file.py:99")
        self.assertEqual(first["subject_kind"], "work")
        self.assertEqual(first["subject_id"], "T-1446")
        self.assertEqual(first["detail"], "T-1446")
        self.assertEqual(first["detail_hash"], second["detail_hash"])

    def test_ruleset_version_two_changes_the_explicit_compatibility_binding(self):
        legacy = json.dumps(
            {"ruleset_version": 1, "rules": findings.RULE_TABLE},
            sort_keys=True, separators=(",", ":"),
        )
        self.assertEqual(findings.RULESET_VERSION, 2)
        self.assertNotEqual(
            findings.ruleset_fingerprint(), hashlib.sha256(legacy.encode()).hexdigest(),
        )


class BaselineCompatibilityTests(unittest.TestCase):
    def setUp(self):
        debt_fixture.DebtGateFixtureTests.setUp(self)
        old = classify(HANDOFF)
        old.update(detail="T-1446", detail_hash=hashlib.sha256(b"T-1446").hexdigest()[:16])
        self.capture = {"ok": True, "gate": "core", "problems": [old], "warnings": []}
        with patch.object(debt, "capture_findings", return_value=self.capture), patch.object(
            findings, "RULESET_VERSION", 1,
        ):
            made = debt.create_snapshot(self.root, "probe", "legacy v1 baseline")
        self.assertTrue(made.get("ok"), made)
        self.old_id = made["snapshot_id"]
        self.old_path = self.root / debt.DEBT_DIR / f"{self.old_id}.json"
        self.old_bytes = self.old_path.read_bytes()

    def tearDown(self):
        debt_fixture.DebtGateFixtureTests.tearDown(self)

    def test_loading_a_v1_baseline_refuses_by_name_without_rewriting_it(self):
        with self.assertRaises(debt.DebtRefusal) as caught:
            debt.load_snapshot(self.root, self.old_id)
        self.assertEqual(caught.exception.code, "BASELINE_RULESET_CHANGED")
        self.assertIn(self.old_id, str(caught.exception))
        self.assertEqual(self.old_path.read_bytes(), self.old_bytes)

    def test_work_comparison_refuses_the_old_baseline_without_rewriting_it(self):
        with patch.object(debt, "capture_findings", return_value=self.capture):
            result = debt.work_delta(self.root, "T-001", agent="probe", baseline_ref=self.old_id)
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "BASELINE_RULESET_CHANGED", result)
        self.assertEqual(self.old_path.read_bytes(), self.old_bytes)

    def test_a_fresh_v2_snapshot_loads_and_preserves_the_legacy_file(self):
        current = {**self.capture, "problems": [classify(HANDOFF)]}
        with patch.object(debt, "capture_findings", return_value=current):
            made = debt.create_snapshot(self.root, "probe", "fresh v2 baseline")
        self.assertTrue(made.get("ok"), made)
        self.assertNotEqual(made["snapshot_id"], self.old_id)
        loaded = debt.load_snapshot(self.root, made["snapshot_id"])
        self.assertEqual(loaded["ruleset_version"], 2)
        self.assertIn("root-file-set", loaded["problems"][0]["detail"])
        self.assertIn("tuple[bool", loaded["problems"][0]["detail"])
        self.assertEqual(self.old_path.read_bytes(), self.old_bytes)


if __name__ == "__main__":
    unittest.main()
