"""T-2040: native finish proposals and closure routing share zero-write truth.

Run: python -B -m unittest discover -s tools -p test_t2040_finish_plan_guards.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from test_hermetic_env import isolate_host_session
from test_request_clause_closure import drive
from test_t1363_zero_manual_entry import healthy, receipts_of
from test_t2040_maintenance_authority import snapshot, source
from saipen_engine import closure_readiness, intake, operations
from saipen_engine.distribution import distribution_record_rel, quarantine_body_rel
from saipen_engine.journal import hash_file_dependency
from saipen_engine.plan import OperationPlan, apply_plan


def setUpModule():
    isolate_host_session()


class FinishProposalGuards(unittest.TestCase):
    def fixture(self):
        root = healthy(self)
        drive(self, root)
        return root

    def test_compound_empty_contract_is_not_predicted_ready(self):
        root = self.fixture()
        source(self, root, "1. Repair the parser\n2. Preserve packaging metadata", "T-1")
        before = snapshot(root)
        decision = closure_readiness.closure_readiness(root, "T-1")
        self.assertFalse(decision["ready"], decision)
        self.assertTrue(decision["canonical_next_command"])
        self.assertEqual(snapshot(root), before)

    def test_foreign_request_clause_owner_is_not_predicted_settleable(self):
        root = self.fixture()
        receipt = receipts_of(root)[0]
        self.assertTrue(intake.ensure_request_clause(root, receipt)["ok"])
        ledger = intake._read_coverage(root, receipt)
        ledger["requirements"][f"{receipt}:R001"]["work"] = "T-999"
        intake._write_coverage(root, receipt, ledger)
        before = snapshot(root)
        decision = closure_readiness.closure_readiness(root, "T-1")
        self.assertFalse(decision["ready"], decision)
        self.assertIn("ACTIVE_DEPENDENCY:T-999", decision["canonical_next_command"])
        self.assertEqual(snapshot(root), before)

    def test_readonly_remediation_never_seeds_request(self):
        root = self.fixture()
        receipt = receipts_of(root)[0]
        gate = intake.work_closure_gate(root, "T-1")
        self.assertEqual(gate["receipt"], receipt)
        before = snapshot(root)
        route = closure_readiness._remediation(root, "T-1", gate, [])
        self.assertTrue(route)
        self.assertEqual(snapshot(root), before)

    def test_generic_work_proof_cannot_retain_stale_live_evidence_class(self):
        root = self.fixture()
        receipt = source(self, root, "[LIVE_END_TO_END] Observe live host acceptance", "T-1")
        self.assertTrue(intake.ensure_request_clause(root, receipt)["ok"])
        ledger = intake._read_coverage(root, receipt)
        ledger["requirements"][f"{receipt}:R001"]["actual_evidence_class"] = "LIVE_END_TO_END"
        intake._write_coverage(root, receipt, ledger)
        before = snapshot(root)
        proposed = intake.plan_request_clause_closure(
            root, "T-1", evidence="T-1 verified code only", verification="T-1 VERIFY cycle in LOG"
        )
        self.assertTrue(proposed["ok"], proposed)
        self.assertFalse(proposed["gate"]["ok"], proposed)
        self.assertEqual(snapshot(root), before)

    def test_plan_pins_distribution_absence_and_protected_body_absence(self):
        root = self.fixture()
        receipt = receipts_of(root)[0]
        proposed = intake.plan_request_clause_closure(
            root, "T-1", evidence="T-1 code verification", verification="T-1 VERIFY cycle in LOG"
        )
        self.assertTrue(proposed["ok"], proposed)
        for rel in (distribution_record_rel(receipt), quarantine_body_rel(receipt)):
            self.assertEqual(proposed["preconditions"].get(rel), hash_file_dependency(root / rel))

    def test_planned_request_evidence_preserves_native_refusals(self):
        root = self.fixture()
        cases = (
            ("", "T-1 VERIFY cycle in LOG", "VALIDATION_FAILED"),
            ("T-1 code verification", "PASS", "VALIDATION_FAILED"),
            ("SRC-999 code verification", "T-1 VERIFY cycle in LOG", "EVIDENCE_IDENTITY_MISMATCH"),
            ("partial fulfillment only", "T-1 VERIFY cycle in LOG", "PARTIAL_FULFILLMENT_REFUSED"),
            ("T-1 code verification", "pytest test_missing_oracle.py", "EVIDENCE_NOT_FOUND"),
        )
        before = snapshot(root)
        for evidence, verification, code in cases:
            with self.subTest(code=code, evidence=evidence, verification=verification):
                proposed = intake.plan_request_clause_closure(
                    root, "T-1", evidence=evidence, verification=verification
                )
                self.assertFalse(proposed["ok"], proposed)
                self.assertEqual(proposed["code"], code, proposed)
                self.assertEqual(snapshot(root), before)

    def test_source_changed_after_plan_refuses_before_any_other_write(self):
        root = self.fixture()
        planned = operations._plan_finish_ticket(
            root, "T-1", "test-agent", operations._now(), operations._utc_iso()
        )
        self.assertIsInstance(planned, OperationPlan, planned)
        receipt = receipts_of(root)[0]
        path = root / f".saipen/intake/active/{receipt}.md"
        path.write_bytes(path.read_bytes() + b"\nfixture source drift\n")
        before = snapshot(root)
        result = apply_plan(root, planned)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
