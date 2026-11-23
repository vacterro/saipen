"""Focused regression suite for source-contract derivation and acceptance fidelity
(T-1814 / SRC-273).

Verifies Regressions A..L and Live Negative Acceptance:
A. Fabricated nonexistent test PASS is refused.
B. Correctly formatted but unexecuted PASS is refused.
C. Authentic execution receipt is accepted for its matching requirement.
D. Authentic but unrelated execution receipt is refused.
E. Stale or tampered execution receipt is refused.
F. Generic core-unit evidence cannot satisfy real host acceptance.
G. Nested 1.1 / 1.2 requirements cannot be discharged by proof covering only 1.1.
H. Multi-section requests preserve all material outcome and safety obligations.
I. SRC-272 remains immutable; its known gaps are handled through a valid corrective receipt.
J. Existing simple atomic requests still work.
K. Legitimate external provenance is not rejected merely for containing another
   source receipt identifier.
L. Existing T-1808/T-1810/T-1811/T-1812/T-1813 lifecycle and source integrity
   contracts remain valid.

Plus Live Negative Acceptance end-to-end 8-step verification.
"""

from __future__ import annotations

import hashlib
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

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from saipen_engine import intake, operations  # noqa: E402
from saipen_engine.journal import ensure_project_lineage  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

ROOT = TOOLS.parent

SAMPLE_NESTED_SUBSECTIONS = """# User request

priority: P1
verify: the requested change is present and demonstrated

## Request

SAIPEN

SAIHANDOFF — NESTED SUBSECTIONS TEST

============================================================
1. ARCHITECTURE FOUNDATION
============================================================

1.1 Core database schema integrity
1.2 Migration pipeline safety

============================================================
2. ENGINE CONTRACTS
============================================================

2.1 Ingress contract validation
2.2 Closure gate verification
"""

SAMPLE_UNNUMBERED_SECTIONS = """# User request

priority: P1
verify: the requested change is present and demonstrated

## Request

SAIPEN

SAIHANDOFF — UNNUMBERED SECTIONS

============================================================
FIRST DELIVERABLE SCOPE
============================================================

Implement parser enhancement for multi-section documents.

============================================================
SECOND DELIVERABLE SCOPE
============================================================

Implement verification proof quality checks.
"""

SAMPLE_SINGLE_ACTION = """# User request

priority: P1
verify: docstring is added

## Request

add a one-line docstring to the top of src/app.py
"""


def setUpModule() -> None:
    isolate_host_session()


class SourceContractDerivationTests(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp(prefix="saipen-t1814-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.base = tmp / "project"
        # These tests isolate clause mapping after execution authentication.
        # The journal-backed reader itself is exercised by T-1908/T-1711.
        proof = patch(
            "saipen_engine.regression_execution.authenticated_record",
            side_effect=lambda root, relative: json.loads((Path(root) / relative).read_text())
            if relative.startswith(".saipen/evidence/regression/")
            and (Path(root) / relative).is_file()
            else None,
        )
        proof.start()
        self.addCleanup(proof.stop)
        oracles = patch(
            "saipen_engine.regression_execution.oracle_files_for_record",
            side_effect=lambda _root, record: set(record["oracle_files"]),
        )
        oracles.start()
        self.addCleanup(oracles.stop)
        (self.base / ".saipen").mkdir(parents=True)
        (self.base / ".saipen" / "STATE.md").write_text(
            "---\n"
            "phase: DONE\n"
            "task: none\n"
            'next_action: "saipen continue"\n'
            'blocker: ""\n'
            "transition_from: DONE\n"
            "saipen_version: 8\n"
            "schema_version: 3\n"
            "last_event: 1\n"
            f"style_contract: {CURRENT_STYLE_CONTRACT}\n"
            f'saipen_home: "{str(ROOT).replace(chr(92), chr(92) * 2)}"\n'
            "agent: tester\n"
            "requires:\n  - filesystem\n  - python\n"
            "mode: full\n"
            'updated: "2026-10-18T00:00:00Z"\n'
            "---\n",
            encoding="utf-8",
        )
        (self.base / ".saipen" / "BOARD.md").write_text(
            "## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
        )
        (self.base / ".saipen" / "LOG.md").write_text(
            "- 18.10.26 00:00 [E-001] [agent: tester] RUN: fixture -> PASS\n",
            encoding="utf-8",
        )
        ensure_project_lineage(self.base)
        self.ev_dir = self.base / ".saipen" / "evidence" / "regression"
        self.ev_dir.mkdir(parents=True)

    def test_regression_a_fabricated_nonexistent_test_pass_refused(self):
        from saipen_engine.operations import ticket_add

        added = ticket_add(self.base, "tester", "P1", "test A", [], "verify test")
        work = added.data["ticket"]
        cap = intake.capture(
            self.base, SAMPLE_SINGLE_ACTION, source_kind="user_instruction", work=work
        )
        rcpt = cap["receipt"]
        intake.ensure_request_clause(self.base, rcpt)

        bad = intake.set_disposition(
            self.base,
            rcpt,
            "R001",
            "VERIFIED",
            work=work,
            evidence="Ran imaginary test",
            verification="python -m unittest tools/test_nonexistent_phantom_module.py -> PASS",
        )
        self.assertFalse(bad.get("ok"))
        self.assertEqual(bad.get("code"), "EVIDENCE_NOT_FOUND")
        self.assertIn("does not exist", bad.get("detail", ""))

    def test_regression_b_correctly_formatted_unexecuted_pass_refused(self):
        from saipen_engine.operations import ticket_add

        added = ticket_add(self.base, "tester", "P1", "test B", [], "verify test")
        work = added.data["ticket"]
        cap = intake.capture(
            self.base, SAMPLE_SINGLE_ACTION, source_kind="user_instruction", work=work
        )
        rcpt = cap["receipt"]
        intake.ensure_request_clause(self.base, rcpt)

        # Create the test file on disk so it exists, but do NOT execute it (no execution receipt)
        unexec = self.base / "tools" / "test_unexecuted_sample.py"
        unexec.parent.mkdir(parents=True, exist_ok=True)
        unexec.write_text("import unittest\n", encoding="utf-8")

        bad = intake.set_disposition(
            self.base,
            rcpt,
            "R001",
            "VERIFIED",
            work=work,
            evidence="tools/test_unexecuted_sample.py verified",
            verification="python -m unittest tools/test_unexecuted_sample.py -> PASS",
        )
        self.assertFalse(bad.get("ok"))
        self.assertEqual(bad.get("code"), "EVIDENCE_UNAUTHENTICATED")
        self.assertIn("no authentic execution receipt found", bad.get("detail", ""))

    def test_regression_c_authentic_execution_receipt_accepted(self):
        from saipen_engine.operations import ticket_add

        added = ticket_add(self.base, "tester", "P1", "test C", [], "verify test")
        work = added.data["ticket"]
        cap = intake.capture(
            self.base, SAMPLE_SINGLE_ACTION, source_kind="user_instruction", work=work
        )
        rcpt = cap["receipt"]
        intake.ensure_request_clause(self.base, rcpt)

        test_file = self.base / "tools" / "test_genuine_feature.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("import unittest\n", encoding="utf-8")

        rec_path = self.ev_dir / "regression-execution-genuine-001.json"
        rec_data = {
            "op_id": "regression-execution-genuine-001",
            "evidence_class": "executed",
            "ticket": work,
            "oracle_files": ["tools/test_genuine_feature.py"],
            "after": {"result": "PASS"},
            "runs": [{"exit_code": 0, "failed": 0}],
        }
        rec_raw = json.dumps(rec_data, indent=2).encode("utf-8")
        rec_path.write_bytes(rec_raw)
        rec_sha = hashlib.sha256(rec_raw).hexdigest()

        good = intake.set_disposition(
            self.base,
            rcpt,
            "R001",
            "VERIFIED",
            work=work,
            evidence=f"tools/test_genuine_feature.py verified record:{rec_path.as_posix()}",
            verification=f"python -m unittest tools/test_genuine_feature.py -> PASS "
            f"(record: .saipen/evidence/regression/{rec_path.name} "
            f"sha256:{rec_sha})",
        )
        self.assertTrue(good.get("ok"), good)
        self.assertEqual(good.get("code"), "COVERAGE_UPDATED")
        self.assertEqual(good.get("disposition"), "VERIFIED")

    def test_regression_d_authentic_but_unrelated_execution_receipt_refused(self):
        from saipen_engine.operations import ticket_add

        added = ticket_add(self.base, "tester", "P1", "parser work", [], "verify parser")
        work = added.data["ticket"]
        doc = (
            "# User request\n\npriority: P1\nverify: test\n\n## Request\n\n"
            "============================================================\n"
            "1. INTAKE PARSER ENHANCEMENT\n"
            "============================================================\n\n"
            "Enhance intake parser extraction logic for discrete clauses.\n\n"
            "============================================================\n"
            "2. MATRIX VERIFICATION\n"
            "============================================================\n\n"
            "Reconcile matrix verification.\n"
        )
        cap = intake.capture(self.base, doc, source_kind="user_instruction", work=work)
        rcpt = cap["receipt"]
        intake.ensure_request_clause(self.base, rcpt)

        # Authentic execution receipt exists, but for revalidation
        reval = self.base / "tools" / "test_external_revalidation.py"
        reval.parent.mkdir(parents=True, exist_ok=True)
        reval.write_text("import unittest\n", encoding="utf-8")

        rec_path = self.ev_dir / "regression-execution-reval-001.json"
        rec_data = {
            "op_id": "regression-execution-reval-001",
            "evidence_class": "executed",
            "oracle_files": ["tools/test_external_revalidation.py"],
            "after": {"result": "PASS"},
            "runs": [{"exit_code": 0, "failed": 0}],
        }
        rec_path.write_bytes(json.dumps(rec_data).encode("utf-8"))

        bad = intake.set_disposition(
            self.base,
            rcpt,
            "R001",
            "VERIFIED",
            work=work,
            evidence="Revalidation suite execution",
            verification=f"python -m unittest tools/test_external_revalidation.py -> "
            f"PASS (record: .saipen/evidence/regression/{rec_path.name})",
        )
        self.assertFalse(bad.get("ok"))
        self.assertEqual(bad.get("code"), "EVIDENCE_UNRELATED")
        self.assertIn("unrelated", bad.get("detail", ""))

    def test_regression_e_stale_or_tampered_execution_receipt_refused(self):
        from saipen_engine.operations import ticket_add

        added = ticket_add(self.base, "tester", "P1", "test E", [], "verify test")
        work = added.data["ticket"]
        cap = intake.capture(
            self.base, SAMPLE_SINGLE_ACTION, source_kind="user_instruction", work=work
        )
        rcpt = cap["receipt"]
        intake.ensure_request_clause(self.base, rcpt)

        test_file = self.base / "tools" / "test_tampered_feature.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("import unittest\n", encoding="utf-8")

        rec_path = self.ev_dir / "regression-execution-tampered-001.json"
        rec_data = {
            "op_id": "regression-execution-tampered-001",
            "evidence_class": "executed",
            "ticket": work,
            "oracle_files": ["tools/test_tampered_feature.py"],
            "after": {"result": "PASS"},
            "tampered": True,
        }
        rec_path.write_bytes(json.dumps(rec_data).encode("utf-8"))

        bad = intake.set_disposition(
            self.base,
            rcpt,
            "R001",
            "VERIFIED",
            work=work,
            evidence="tools/test_tampered_feature.py verified",
            verification=f"python -m unittest tools/test_tampered_feature.py -> PASS "
            f"(record: .saipen/evidence/regression/{rec_path.name})",
        )
        self.assertFalse(bad.get("ok"))
        self.assertEqual(bad.get("code"), "EVIDENCE_CORRUPTION")

    def test_regression_f_generic_core_unit_evidence_cannot_satisfy_real_host_acceptance(self):
        from saipen_engine.operations import ticket_add

        added = ticket_add(self.base, "tester", "P1", "host work", [], "verify host")
        work = added.data["ticket"]
        doc = (
            "# User request\n\npriority: P1\nverify: test\n\n## Request\n\n"
            "============================================================\n"
            "1. LIVE HOST ACCEPTANCE GATEWAY\n"
            "============================================================\n\n"
            "Execute live host acceptance probe against live session.\n\n"
            "============================================================\n"
            "2. REPORTING\n"
            "============================================================\n\n"
            "Report outcomes.\n"
        )
        cap = intake.capture(self.base, doc, source_kind="user_instruction", work=work)
        rcpt = cap["receipt"]
        intake.ensure_request_clause(self.base, rcpt)

        bad = intake.set_disposition(
            self.base,
            rcpt,
            "R001",
            "VERIFIED",
            work=work,
            evidence="Run core unit test suite",
            verification="python tools/run_tests.py core-unit -> aggregate core pass",
        )
        self.assertFalse(bad.get("ok"))
        self.assertEqual(bad.get("code"), "EVIDENCE_SCOPE_TOO_WEAK")
        self.assertIn(
            "authentic live receipt required", bad.get("detail", "")
        )

    def test_regression_g_nested_subrequirements_cannot_be_discharged_by_partial_proof(self):
        from saipen_engine.operations import ticket_add

        added = ticket_add(self.base, "tester", "P1", "nested work", [], "verify nested")
        work = added.data["ticket"]
        cap = intake.capture(
            self.base, SAMPLE_NESTED_SUBSECTIONS, source_kind="user_instruction", work=work
        )
        rcpt = cap["receipt"]
        derived = intake.ensure_request_clause(self.base, rcpt)
        self.assertTrue(derived.get("ok"))

        # SAMPLE_NESTED_SUBSECTIONS extracts 4 clauses: R001: 1.1, R002: 1.2, R003: 2.1, R004: 2.2
        ledger = intake.coverage_summary(self.base, rcpt)
        self.assertEqual(ledger["requirements"], 4)

        t1 = self.base / "tools" / "test_outcome_1_schema.py"
        t1.parent.mkdir(parents=True, exist_ok=True)
        t1.write_text("import unittest\n", encoding="utf-8")

        rec1 = self.ev_dir / "regression-execution-subreq-001.json"
        rec1_data = {
            "op_id": "regression-execution-subreq-001",
            "evidence_class": "executed",
            "ticket": work,
            "requirement": "R001",
            "oracle_files": ["tools/test_outcome_1_schema.py"],
            "after": {"result": "PASS"},
            "runs": [{"exit_code": 0, "failed": 0}],
        }
        rec1.write_bytes(json.dumps(rec1_data).encode("utf-8"))

        good1 = intake.set_disposition(
            self.base,
            rcpt,
            "R001",
            "VERIFIED",
            work=work,
            evidence="schema verified",
            verification=f"python -m unittest tools/test_outcome_1_schema.py -> PASS "
            f"(record: .saipen/evidence/regression/{rec1.name})",
        )
        self.assertTrue(good1.get("ok"))

        # Attempt to discharge 1.2 (R002) using the 1.1 receipt
        bad2 = intake.set_disposition(
            self.base,
            rcpt,
            "R002",
            "VERIFIED",
            work=work,
            evidence="pipeline verified using same receipt",
            verification=f"python -m unittest tools/test_outcome_1_schema.py -> PASS "
            f"(record: .saipen/evidence/regression/{rec1.name})",
        )
        self.assertFalse(bad2.get("ok"))
        self.assertEqual(bad2.get("code"), "EVIDENCE_UNRELATED")

        # Prove R002 remains unresolved
        summary = intake.coverage_summary(self.base, rcpt)
        self.assertIn(f"{rcpt}:R002", summary["unresolved"])

    def test_regression_h_multisection_requests_preserve_all_material_obligations(self):
        archive_src272 = ROOT / ".saipen" / "archive" / "source" / "SRC-272.md"
        self.assertTrue(archive_src272.exists())
        clauses = intake.extract_request_clauses(archive_src272.read_text(encoding="utf-8"))
        self.assertGreaterEqual(
            len(clauses), 14, f"Expected all material obligations preserved, got {len(clauses)}"
        )
        self.assertTrue(any(c.startswith("GAP 1:") for c in clauses))
        self.assertTrue(any(c.startswith("MISSION:") for c in clauses))
        self.assertTrue(any(c.startswith("TEST A:") for c in clauses))
        self.assertTrue(any(c.startswith("TEST J:") for c in clauses))
        self.assertTrue(any(c.startswith("RECONCILIATION:") for c in clauses))
        self.assertTrue(any(c.startswith("SUCCESS:") for c in clauses))

    def test_regression_i_src272_remains_immutable_with_valid_corrective_receipt(self):
        archive_src272 = ROOT / ".saipen" / "archive" / "source" / "SRC-272.md"
        archive_meta = ROOT / ".saipen" / "archive" / "source" / "SRC-272.meta.json"
        archive_contract = ROOT / ".saipen" / "archive" / "source" / "SRC-272.contract.json"
        self.assertTrue(archive_src272.exists())
        self.assertTrue(archive_meta.exists())
        self.assertTrue(archive_contract.exists())

        mdata = json.loads(archive_meta.read_text(encoding="utf-8"))
        cdata = json.loads(archive_contract.read_text(encoding="utf-8"))
        actual_sha = hashlib.sha256(archive_src272.read_bytes()).hexdigest()
        self.assertEqual(mdata["source_sha256"], actual_sha)
        self.assertEqual(cdata["source_sha256"], actual_sha)

        # SRC-273 closed with T-1814 and is therefore archived; active bytes
        # for a closed receipt are residue, not authority (intake.py
        # _settle_closed_residue_locked). The valid corrective successor is
        # the archived body, not a restored hot-surface copy.
        archive_src273 = ROOT / ".saipen" / "archive" / "source" / "SRC-273.md"
        self.assertTrue(archive_src273.exists())

    def test_regression_j_existing_simple_atomic_requests_still_work(self):
        clauses = intake.extract_request_clauses(SAMPLE_SINGLE_ACTION)
        self.assertEqual(len(clauses), 0)

        cap = intake.capture(self.base, SAMPLE_SINGLE_ACTION, source_kind="user_instruction")
        rcpt = cap["receipt"]
        derived = intake.ensure_request_clause(self.base, rcpt)
        self.assertTrue(derived.get("ok"))
        summary = intake.coverage_summary(self.base, rcpt)
        self.assertEqual(summary["requirements"], 1)
        self.assertIn(f"{rcpt}:R001", summary["unresolved"])

    def test_regression_k_legitimate_external_provenance_not_rejected_for_foreign_receipt_id(self):
        from saipen_engine.operations import ticket_add

        added = ticket_add(self.base, "tester", "P1", "test K", [], "verify test")
        work = added.data["ticket"]
        cap = intake.capture(
            self.base, SAMPLE_SINGLE_ACTION, source_kind="user_instruction", work=work
        )
        rcpt = cap["receipt"]
        intake.ensure_request_clause(self.base, rcpt)

        good = intake.set_disposition(
            self.base,
            rcpt,
            "R001",
            "VERIFIED",
            work=work,
            evidence="External provenance: amends SRC-269 via upstream commit 5f0dc0c",
            verification="external: upstream fix verified",
        )
        self.assertTrue(good.get("ok"), good)
        self.assertEqual(good.get("code"), "COVERAGE_UPDATED")

    def test_regression_l_existing_lifecycle_contracts_remain_valid(self):
        from saipen_engine.operations import ticket_add

        added = ticket_add(self.base, "tester", "P1", "test L", [], "verify test")
        work = added.data["ticket"]
        cap = intake.capture(
            self.base, SAMPLE_SINGLE_ACTION, source_kind="user_instruction", work=work
        )
        rcpt = cap["receipt"]
        intake.ensure_request_clause(self.base, rcpt)

        contract_path = self.base / ".saipen" / "intake" / "contracts" / f"{rcpt}.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["clauses"][f"{rcpt}:R001"]["when_environment"] = "posix_symlink"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        refused_waiver = intake.set_disposition(
            self.base, rcpt, "R001", "UNAVAILABLE_ENVIRONMENT", work=work
        )
        self.assertFalse(refused_waiver.get("ok"))
        self.assertEqual(refused_waiver.get("code"), "ENVIRONMENT_WAIVER_REFUSED")

        # Source corruption check
        body_path = self.base / ".saipen" / "intake" / "active" / f"{rcpt}.md"
        body_path.write_text("tampered body content", encoding="utf-8")
        bad = intake.set_disposition(
            self.base,
            rcpt,
            "R001",
            "VERIFIED",
            evidence="external observation",
            verification="manual: PASS",
        )
        self.assertFalse(bad.get("ok"))
        self.assertEqual(bad.get("code"), "SOURCE_CORRUPTION")

    def test_live_negative_acceptance_end_to_end(self):
        """End-to-end 8-step live negative acceptance flow in disposable canonical project:

        1. Create an admitted ticket with two independently required acceptance outcomes.
        2. Produce genuine verification evidence for only one.
        3. Attempt to mark both VERIFIED using the same receipt.
        4. Prove the unrelated second requirement remains open.
        5. Attempt ticket completion.
        6. Prove canonical closure refuses.
        7. Generate legitimate evidence for the second outcome.
        8. Prove normal closure succeeds.
        """
        # Step 1: Create an admitted ticket with two independently required acceptance outcomes
        two_outcomes_doc = (
            "# User request\n\npriority: P1\nverify: test\n\n## Request\n\n"
            "============================================================\n"
            "1. DATABASE SUBSYSTEM\n"
            "============================================================\n\n"
            "1.1 Core database schema integrity\n\n"
            "============================================================\n"
            "2. PIPELINE SUBSYSTEM\n"
            "============================================================\n\n"
            "2.1 Migration pipeline safety\n"
        )
        add_res = operations.ticket_add(self.base, "tester", "P1", "two outcomes", [], "verify e2e")
        self.assertTrue(add_res.ok, add_res.data)
        ticket_id = add_res.data["ticket"]

        cap = intake.capture(
            self.base, two_outcomes_doc, source_kind="user_instruction", work=ticket_id
        )
        rcpt = cap["receipt"]
        derived = intake.ensure_request_clause(self.base, rcpt)
        self.assertTrue(derived.get("ok"))

        # Transition ticket to DOING
        operations.apply_claim(self.base, ticket_id, "tester")
        operations.transition_phase(self.base, "BUILD", "tester", ticket_id=ticket_id)
        operations.checkpoint(
            self.base, "tester", "RUN", ticket_id, "build -> implemented two subsystems"
        )

        summary = intake.coverage_summary(self.base, rcpt)
        self.assertEqual(summary["requirements"], 2)
        r1, r2 = sorted(summary["unresolved"])

        # Step 2: Produce genuine verification evidence for only one
        t1 = self.base / "tools" / "test_outcome1_schema.py"
        t1.parent.mkdir(parents=True, exist_ok=True)
        t1.write_text("import unittest\n", encoding="utf-8")

        rec1 = self.ev_dir / "regression-execution-e2e-001.json"
        rec1_data = {
            "op_id": "regression-execution-e2e-001",
            "evidence_class": "executed",
            "ticket": ticket_id,
            "requirement": r1.split(":")[-1],
            "oracle_files": ["tools/test_outcome1_schema.py"],
            "after": {"result": "PASS"},
            "runs": [{"exit_code": 0, "failed": 0}],
        }
        rec1.write_bytes(json.dumps(rec1_data).encode("utf-8"))

        disp1 = intake.set_disposition(
            self.base,
            rcpt,
            r1.split(":")[-1],
            "VERIFIED",
            work=ticket_id,
            evidence="schema verified",
            verification=f"python -m unittest tools/test_outcome1_schema.py -> PASS "
            f"(record: .saipen/evidence/regression/{rec1.name})",
        )
        self.assertTrue(disp1.get("ok"), disp1)

        # Step 3: Attempt to mark both VERIFIED using the same receipt
        disp2_bad = intake.set_disposition(
            self.base,
            rcpt,
            r2.split(":")[-1],
            "VERIFIED",
            work=ticket_id,
            evidence="pipeline verified using schema receipt",
            verification=f"python -m unittest tools/test_outcome1_schema.py -> PASS "
            f"(record: .saipen/evidence/regression/{rec1.name})",
        )

        # Step 4: Prove the unrelated second requirement remains open
        self.assertFalse(disp2_bad.get("ok"))
        self.assertEqual(disp2_bad.get("code"), "EVIDENCE_UNRELATED")
        summary_after = intake.coverage_summary(self.base, rcpt)
        self.assertIn(r2, summary_after["unresolved"])
        self.assertFalse(intake.coverage_complete(self.base, rcpt))

        # Step 5: Attempt ticket completion
        # Transition to VERIFY -> REVIEW -> SHIP
        operations.transition_phase(self.base, "VERIFY", "tester", ticket_id=ticket_id)
        operations.checkpoint(
            self.base,
            "tester",
            "RUN",
            ticket_id,
            f"verify -> PASS [target: {ticket_id}] conf: high -- tests passed",
        )
        operations.transition_phase(self.base, "REVIEW", "tester", ticket_id=ticket_id)
        operations.transition_phase(self.base, "SHIP", "tester", ticket_id=ticket_id)

        closure_gate = intake.work_closure_gate(self.base, ticket_id)
        # Step 6: Prove canonical closure refuses
        self.assertFalse(closure_gate.get("ok"))
        self.assertEqual(closure_gate.get("code"), "SOURCE_UNRESOLVED")
        refused_finish = operations.finish_ticket(self.base, ticket_id, "tester")
        self.assertFalse(refused_finish.ok)
        self.assertEqual(refused_finish.code, "SOURCE_UNRESOLVED")

        # Step 7: Generate legitimate evidence for the second outcome
        t2 = self.base / "tools" / "test_outcome2_pipeline.py"
        t2.write_text("import unittest\n", encoding="utf-8")

        rec2 = self.ev_dir / "regression-execution-e2e-002.json"
        rec2_data = {
            "op_id": "regression-execution-e2e-002",
            "evidence_class": "executed",
            "ticket": ticket_id,
            "requirement": r2.split(":")[-1],
            "oracle_files": ["tools/test_outcome2_pipeline.py"],
            "after": {"result": "PASS"},
            "runs": [{"exit_code": 0, "failed": 0}],
        }
        rec2.write_bytes(json.dumps(rec2_data).encode("utf-8"))

        disp2_good = intake.set_disposition(
            self.base,
            rcpt,
            r2.split(":")[-1],
            "VERIFIED",
            work=ticket_id,
            evidence="pipeline verified",
            verification=f"python -m unittest tools/test_outcome2_pipeline.py -> PASS "
            f"(record: .saipen/evidence/regression/{rec2.name})",
        )
        self.assertTrue(disp2_good.get("ok"), disp2_good)

        # Step 8: Prove normal closure succeeds
        summary_final = intake.coverage_summary(self.base, rcpt)
        self.assertEqual(len(summary_final["unresolved"]), 0)
        self.assertTrue(intake.coverage_complete(self.base, rcpt))

        done_res = operations.finish_ticket(self.base, ticket_id, "tester")
        self.assertTrue(done_res.ok, getattr(done_res, "message", done_res.data))
        self.assertEqual(done_res.code, "FINISHED")


if __name__ == "__main__":
    unittest.main()
