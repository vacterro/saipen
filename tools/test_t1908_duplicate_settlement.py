"""T-1908 / SRC-323: a proven duplicate must not deadlock on its own Source.

Measured class (ZAICODE A3 Quick3, 2026-10-25): Work that already owned a
Source could neither be superseded (OLD carries `source_receipts`) nor have its
Source retired (`source_retirement_errors` refuses while live Work references
it). The agent had the right answer -- no implementation delta -- and asked a
human to inspect protocol internals anyway.

The cure keeps BOTH protections: the same PASS event the operator capsule
already names discharges the receipt's OWN request clause in the same journaled
transaction, and any other unresolved requirement refuses, naming the exact
`saipen source disp` command that settles it on its own evidence.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import debt, intake, journal, operations  # noqa: E402
from saipen_engine.board import parse_board, set_ticket_field  # noqa: E402
from saipen_engine.entry import (  # noqa: E402
    _bind_duplicate_ingress,
    existing_work_for_request,
    start_work,
)
from saipen_engine.handoff_reconciliation import (  # noqa: E402
    EXISTING_IMPLEMENTATION_UNVERIFIED,
    EXISTING_IMPLEMENTATION_VERIFIED,
    INDEPENDENT_OPERATOR_GATE,
    NEW_IMPLEMENTATION_REQUIRED,
    PARTIAL_OVERLAP,
    REGRESSION_DETECTED,
    VERDICT_CHANGED_CONTRACT,
    VERDICT_MISSING,
    VERDICT_REGRESSION,
    VERDICT_UNVERIFIED,
    VERDICT_VERIFIED,
    analyze_handoff_delta,
    settle_proven_duplicate,
)
from saipen_engine.retirement import source_retirement_errors  # noqa: E402
from test_ticket_supersession import SupersessionFixture, _tree_digest  # noqa: E402

SINGLE_REQUEST = (
    "Deliver the harness-independent A3 Quick3 audit: one canonical audit/ "
    "artifact with a stable producer identity and idempotent publication.\n"
)

# Two discrete clauses: `extract_request_clauses` derives them individually, so
# neither is the request clause itself and this route may not discharge either.
COMPOUND_REQUEST = (
    "Deliver the A3 Quick3 audit.\n\n"
    "1. Publish the canonical audit artifact.\n"
    "2. Bind the producer operation identity.\n"
)


SUCCESSOR_CONTRACT = (
    "verify with a passing test that reads the canonical audit artifact written "
    "by producer wave3"
)


class AttachSourceMixin:
    def add(self, project: Path, description: str, **kwargs) -> str:
        if description == "successor implementation":
            # The successor's own acceptance contract must name what it proves;
            # a terse "verify with a passing test" is a candidate with no
            # content to compare a handoff clause against (SRC-323 §5).
            kwargs.setdefault("verify", SUCCESSOR_CONTRACT)
        ticket = super().add(project, description, **kwargs)
        if description == "successor implementation":
            audit = project / "audit"
            audit.mkdir(exist_ok=True)
            (audit / "A3-quick3.md").write_text(
                "producer: wave3\ncanonical audit artifact\n", encoding="utf-8"
            )
            (project / "verify_existing.py").write_text(
                "from pathlib import Path\n"
                "report = Path('audit/A3-quick3.md').read_text(encoding='utf-8')\n"
                "assert 'producer: wave3' in report\n"
                "assert 'canonical audit artifact' in report\n",
                encoding="utf-8",
            )
        return ticket

    def attach_source(
        self, project: Path, text: str = SINGLE_REQUEST, *, verified_successor: bool = True
    ) -> str:
        """Capture a real receipt, derive its clauses, bind it to T-7."""
        board_path = project / ".saipen" / "BOARD.md"
        if verified_successor:
            done = [
                work for work, row in parse_board(board_path.read_text())["tickets"].items()
                if row["section"] == "## DONE"
            ]
            self.assertEqual(len(done), 1, done)
            verified = debt.reverify_work(
                project, done[0], "tester", runs=["python verify_existing.py"]
            )
            self.assertTrue(verified["ok"], verified)
            self.assertIn(verified["verdict"], {"PASS", "PASS_WITH_CARRIED_DEBT"}, verified)
        captured = intake.capture(project, text, source_kind="user_instruction")
        self.assertTrue(captured["ok"], captured)
        receipt = captured["receipt"]
        derived = intake.ensure_request_clause(project, receipt)
        self.assertTrue(derived["ok"], derived)
        board = board_path.read_text(encoding="utf-8")
        ticket = parse_board(board)["tickets"]["T-7"]
        board_path.write_text(
            board.replace(
                ticket["raw"],
                set_ticket_field(ticket["raw"], "source_receipts", receipt),
            ),
            encoding="utf-8",
        )
        if verified_successor:
            self.assertIsNotNone(debt.current_tree_reverify(project, done[0]))
        return receipt

    def ledger(self, project: Path, receipt: str) -> dict:
        return intake._read_coverage(project, receipt)


class DeadlockReproductionTests(AttachSourceMixin, SupersessionFixture):
    """The two halves of the cycle, pinned before the cure in each test."""

    def test_source_of_live_work_cannot_be_retired(self):
        project, _successor, _evidence, _authority = self.prepare()
        receipt = self.attach_source(project)
        problems = source_retirement_errors(
            project,
            receipt,
            reason="ORPHANED_RECEIPT",
            successor=None,
            note=None,
        )
        self.assertTrue(
            any("is the source of live Work" in problem for problem in problems),
            problems,
        )

    def test_already_satisfied_duplicate_settles_through_the_successor(self):
        project, successor, evidence, authority = self.prepare()
        receipt = self.attach_source(project)

        result = self.supersede(project, successor, evidence, authority)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.code, "SUPERSEDED")

        summary = intake.coverage_summary(project, receipt)
        self.assertEqual(summary["requirements"], 1, summary)
        self.assertEqual(summary["unresolved"], [], summary)

        entry = self.ledger(project, receipt)["requirements"][f"{receipt}:R001"]
        self.assertEqual(entry["disposition"], "VERIFIED")
        self.assertEqual(entry["work"], successor)
        self.assertEqual(entry["evidence"], evidence)
        self.assertIn("-> PASS", entry["verification"])
        self.assertIn("T-7", entry["verification"])
        self.assertIn("reverify: RV-", entry["verification"])

        row = parse_board((project / ".saipen" / "BOARD.md").read_text())["tickets"]["T-7"]
        self.assertEqual(row["section"], "## DONE")
        self.assertEqual(row["fields"]["closure_mode"], "superseded_verified")
        self.assertEqual(row["fields"]["implementation_delta"], "none")

    def test_settlement_breaks_the_cycle_without_retiring_the_source(self):
        project, successor, evidence, authority = self.prepare()
        receipt = self.attach_source(project)
        self.assertTrue(self.supersede(project, successor, evidence, authority).ok)

        problems = source_retirement_errors(
            project,
            receipt,
            reason="ORPHANED_RECEIPT",
            successor=None,
            note=None,
        )
        self.assertFalse(
            any("is the source of live Work" in problem for problem in problems),
            problems,
        )
        self.assertFalse(
            any("unresolved actionable" in problem for problem in problems),
            problems,
        )
        self.assertTrue(intake._read_meta(project, receipt), "the receipt stays ACTIVE")

    def test_identical_repeat_writes_nothing_new(self):
        project, successor, evidence, authority = self.prepare()
        self.attach_source(project)
        self.assertTrue(self.supersede(project, successor, evidence, authority).ok)
        before = _tree_digest(project)
        repeated = self.supersede(project, successor, evidence, authority)
        self.assertTrue(repeated.ok, repeated.to_dict())
        self.assertEqual(repeated.code, "ALREADY_APPLIED")
        self.assertEqual(_tree_digest(project), before)


class PublicCliTests(AttachSourceMixin, SupersessionFixture):
    def test_the_canonical_command_settles_an_already_satisfied_duplicate(self):
        project, successor, evidence, authority = self.prepare()
        receipt = self.attach_source(project)
        proc = self.command(
            project,
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "ticket",
                "supersede",
                "T-7",
                "--by",
                successor,
                "--evidence",
                evidence,
                "--authority",
                authority,
                "--project-root",
                str(project),
                "--agent",
                "tester",
                "--json",
            ],
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["code"], "SUPERSEDED")
        self.assertEqual(payload["source_settlement"], {receipt: [f"{receipt}:R001"]})
        self.assertEqual(intake.coverage_summary(project, receipt)["unresolved"], [])


class UnresolvedClauseTests(AttachSourceMixin, SupersessionFixture):
    def test_agent_checkpoint_alone_cannot_verify_the_source_request(self):
        project, successor, evidence, authority = self.prepare()
        receipt = self.attach_source(project, verified_successor=False)
        before = self.ledger(project, receipt)

        result = self.supersede(project, successor, evidence, authority)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "SUPERSESSION_EVIDENCE_INVALID")
        self.assertEqual(self.ledger(project, receipt), before)

    def test_successor_source_change_after_reverify_invalidates_the_proof(self):
        project, successor, evidence, authority = self.prepare()
        receipt = self.attach_source(project)
        (project / "audit" / "A3-quick3.md").write_text("changed\n", encoding="utf-8")

        result = self.supersede(project, successor, evidence, authority)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "SUPERSESSION_EVIDENCE_INVALID")
        self.assertEqual(
            intake.coverage_summary(project, receipt)["unresolved"], [f"{receipt}:R001"]
        )

    def test_source_change_between_plan_and_apply_is_cas_refused(self):
        project, successor, evidence, authority = self.prepare()
        receipt = self.attach_source(project)
        real_apply = operations.apply_plan

        def mutate_before_apply(root, plan):
            (project / "audit" / "A3-quick3.md").write_text("changed\n", encoding="utf-8")
            return real_apply(root, plan)

        with mock.patch.object(operations, "apply_plan", side_effect=mutate_before_apply):
            result = self.supersede(project, successor, evidence, authority)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "STALE_STATE")
        self.assertEqual(
            intake.coverage_summary(project, receipt)["unresolved"], [f"{receipt}:R001"]
        )

    def test_compound_request_refuses_and_names_the_disp_command(self):
        project, successor, evidence, authority = self.prepare()
        receipt = self.attach_source(project, COMPOUND_REQUEST)
        before = self.ledger(project, receipt)
        result = self.supersede(project, successor, evidence, authority)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "SUPERSESSION_SOURCE_MIGRATION_REQUIRED")
        self.assertIn("saipen source disp", result.message)
        self.assertIn("--work " + successor, result.message)
        self.assertEqual(self.ledger(project, receipt), before)
        row = parse_board((project / ".saipen" / "BOARD.md").read_text())["tickets"]["T-7"]
        self.assertEqual(row["section"], "## BLOCKED")
        self.assertNotIn("supersession_evidence", row["fields"])

    def test_unknown_receipt_still_fails_closed(self):
        project, successor, evidence, authority = self.prepare()
        board_path = project / ".saipen" / "BOARD.md"
        board = board_path.read_text(encoding="utf-8")
        ticket = parse_board(board)["tickets"]["T-7"]
        board_path.write_text(
            board.replace(
                ticket["raw"],
                set_ticket_field(ticket["raw"], "source_receipts", "SRC-999"),
            ),
            encoding="utf-8",
        )
        result = self.supersede(project, successor, evidence, authority)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "SUPERSESSION_SOURCE_MIGRATION_REQUIRED")
        self.assertIn("no active metadata", result.message)

    def test_forged_test_report_cannot_settle_a_fresh_clause(self):
        project, successor, _evidence, _authority = self.prepare()
        receipt = self.attach_source(project, COMPOUND_REQUEST)
        before = self.ledger(project, receipt)
        result = intake.set_disposition(
            project,
            receipt,
            "R001",
            "VERIFIED",
            work=successor,
            evidence="agent says all tests passed",
            verification="python -m pytest tools/test_missing_proof.py -> PASS",
        )
        self.assertFalse(result["ok"], result)
        self.assertIn(result["code"], {"EVIDENCE_NOT_FOUND", "EVIDENCE_UNAUTHENTICATED"})
        self.assertEqual(self.ledger(project, receipt), before)

    def test_hand_written_pass_json_cannot_impersonate_executed_test(self):
        project, successor, _evidence, _authority = self.prepare()
        receipt = self.attach_source(project, COMPOUND_REQUEST, verified_successor=False)
        before = self.ledger(project, receipt)
        test_file = project / "tools" / "test_fake.py"
        test_file.parent.mkdir(exist_ok=True)
        test_file.write_text("def test_fake():\n    assert True\n", encoding="utf-8")
        report = (
            project / ".saipen" / "evidence" / "regression"
            / "regression-execution-fake-pass.json"
        )
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            json.dumps(
                {
                    "op_id": "regression-execution-fake-pass",
                    "evidence_class": "executed",
                    "command": ["python", "-m", "pytest", "tools/test_fake.py"],
                    "oracle_files": ["tools/test_fake.py"],
                    "status": "PASS",
                    "runs": [{"exit_code": 0, "failed": 0}],
                }
            ),
            encoding="utf-8",
        )
        result = intake.set_disposition(
            project,
            receipt,
            "R001",
            "VERIFIED",
            work=successor,
            evidence=".saipen/evidence/regression/regression-execution-fake-pass.json",
            verification=(
                "python -m pytest tools/test_fake.py -> PASS "
                "record: .saipen/evidence/regression/regression-execution-fake-pass.json"
            ),
        )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "EVIDENCE_UNAUTHENTICATED")
        self.assertEqual(self.ledger(project, receipt), before)


class JournalBoundaryTests(AttachSourceMixin, SupersessionFixture):
    def _crash(self, project: Path, successor: str, evidence: str, authority: str, at: str):
        def interrupt(key: str) -> None:
            if key == at:
                raise RuntimeError(f"interrupted after {at}")

        crash_probe = mock.patch.object(journal, "_crash_after", side_effect=interrupt)
        with crash_probe, self.assertRaisesRegex(RuntimeError, f"interrupted after {at}"):
            self.supersede(project, successor, evidence, authority)
        pending = journal.pending_ops(project)
        self.assertEqual(len(pending), 1, pending)
        return pending[0]["op_id"]

    def test_crash_after_prepare_leaves_source_and_work_open(self):
        project, successor, evidence, authority = self.prepare()
        receipt = self.attach_source(project)
        op_id = self._crash(project, successor, evidence, authority, "PREPARED")
        self.assertEqual(
            intake.coverage_summary(project, receipt)["unresolved"], [f"{receipt}:R001"]
        )
        self.assertEqual(
            parse_board((project / ".saipen" / "BOARD.md").read_text())["tickets"]["T-7"][
                "section"
            ],
            "## BLOCKED",
        )

        recovered = journal.recover(project, op_id)
        self.assertTrue(recovered.get("ok"), recovered)
        summary = intake.coverage_summary(project, receipt)
        section = parse_board((project / ".saipen" / "BOARD.md").read_text())["tickets"]["T-7"][
            "section"
        ]
        self.assertEqual(bool(summary["unresolved"]), section != "## DONE")

    def test_crash_after_verified_recovery_keeps_one_terminal_event(self):
        project, successor, evidence, authority = self.prepare()
        receipt = self.attach_source(project)
        op_id = self._crash(project, successor, evidence, authority, "VERIFIED")
        self.assertEqual(intake.coverage_summary(project, receipt)["unresolved"], [])

        recovered = journal.recover(project, op_id)
        self.assertTrue(recovered.get("ok"), recovered)
        before = _tree_digest(project)
        again = journal.recover(project, op_id)
        self.assertTrue(again.get("ok"), again)
        self.assertEqual(_tree_digest(project), before)
        self.assertEqual(journal.pending_ops(project), [])
        self.assertEqual(
            parse_board((project / ".saipen" / "BOARD.md").read_text())["tickets"]["T-7"][
                "section"
            ],
            "## DONE",
        )


class CompoundIngressTests(AttachSourceMixin, SupersessionFixture):
    def test_done_description_without_current_proof_is_only_a_candidate(self):
        project, _successor, _evidence, _authority = self.prepare()
        tickets = {
            "T-7": {
                "section": "## DONE",
                "description": SINGLE_REQUEST,
                "fields": {},
            }
        }
        self.assertIsNone(existing_work_for_request(project, tickets, SINGLE_REQUEST))

    def test_matching_done_description_does_not_swallow_unverified_clauses(self):
        tickets = {
            "T-7": {
                "section": "## DONE",
                "description": COMPOUND_REQUEST,
                "fields": {},
            }
        }
        self.assertIsNone(existing_work_for_request(ROOT, tickets, COMPOUND_REQUEST))

    def test_done_binding_never_blanket_verifies_compound_request(self):
        project, successor, _evidence, _authority = self.prepare()
        captured = intake.capture(project, COMPOUND_REQUEST, source_kind="user_instruction")
        self.assertTrue(captured["ok"], captured)
        receipt = captured["receipt"]
        ticket = parse_board((project / ".saipen" / "BOARD.md").read_text())["tickets"][successor]

        result = _bind_duplicate_ingress(project, receipt, successor, ticket)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "DUPLICATE_CLAUSES_UNVERIFIED")
        ledger = intake._read_coverage(project, receipt)
        self.assertEqual(len(ledger["requirements"]), 2)
        self.assertTrue(
            all(item["disposition"] == "UNKNOWN" for item in ledger["requirements"].values())
        )

    def test_done_binding_without_current_proof_does_not_mark_single_clause_verified(self):
        project, successor, _evidence, _authority = self.prepare()
        captured = intake.capture(project, SINGLE_REQUEST, source_kind="user_instruction")
        self.assertTrue(captured["ok"], captured)
        receipt = captured["receipt"]
        ticket = parse_board((project / ".saipen" / "BOARD.md").read_text())["tickets"][successor]

        result = _bind_duplicate_ingress(project, receipt, successor, ticket)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "DUPLICATE_CURRENT_EVIDENCE_REQUIRED")
        self.assertEqual(
            intake.coverage_summary(project, receipt)["unresolved"], [f"{receipt}:R001"]
        )


class HandoffReconciliationTests(AttachSourceMixin, SupersessionFixture):
    """Pre-admission delta classifier and zero-delta outcome (SRC-323 §4, §5, §12, §13)."""

    def test_substantially_different_text_requires_clause_by_clause_verification(self):
        project, _successor, _evidence, _authority = self.prepare()
        self.attach_source(project, verified_successor=True)
        # Different phrasing of the same audit requirement
        text = (
            "Ensure the A3 Quick3 audit artifact exists in audit/ with wave3 producer identity."
        )
        analysis = analyze_handoff_delta(project, text)
        self.assertEqual(analysis.status, EXISTING_IMPLEMENTATION_VERIFIED)
        self.assertEqual(analysis.implementation_delta, 0)
        self.assertEqual(analysis.clauses_verified_existing, 1)
        self.assertEqual(analysis.matrix[0].equivalence_verdict, VERDICT_VERIFIED)

    def test_one_missing_requirement_leaves_delta_active(self):
        project, _successor, _evidence, _authority = self.prepare()
        self.attach_source(project, verified_successor=True)
        handoff = (
            "Handoff:\n\n"
            "1. Deliver the canonical audit artifact with wave3 producer.\n"
            "2. Deploy the service to external staging cluster.\n"
        )
        analysis = analyze_handoff_delta(project, handoff)
        self.assertEqual(analysis.status, PARTIAL_OVERLAP)
        self.assertEqual(analysis.clauses_total, 2)
        self.assertEqual(analysis.clauses_verified_existing, 1)
        self.assertEqual(analysis.implementation_delta, 1)
        self.assertEqual(analysis.matrix[0].equivalence_verdict, VERDICT_VERIFIED)
        self.assertEqual(analysis.matrix[1].equivalence_verdict, VERDICT_MISSING)

    def test_failing_current_regression_requires_repair(self):
        project, _successor, _evidence, _authority = self.prepare()
        self.attach_source(project, verified_successor=True)
        text = "Deliver the canonical audit artifact with wave3 producer."
        with mock.patch(
            "saipen_engine.debt.current_tree_reverify",
            return_value={
                "receipt_id": "RV-1",
                "verdict": "FAIL",
                "verification": [{"command": "python verify_existing.py", "result": "FAIL"}],
            },
        ):
            analysis = analyze_handoff_delta(project, text)
        self.assertEqual(analysis.status, REGRESSION_DETECTED)
        self.assertEqual(analysis.clauses_require_repair, 1)
        self.assertEqual(analysis.matrix[0].equivalence_verdict, VERDICT_REGRESSION)

    def test_stale_verification_is_unverified(self):
        project, _successor, _evidence, _authority = self.prepare()
        self.attach_source(project, verified_successor=False)
        text = "Deliver the canonical audit artifact with wave3 producer."
        analysis = analyze_handoff_delta(project, text)
        self.assertEqual(analysis.status, EXISTING_IMPLEMENTATION_UNVERIFIED)
        self.assertEqual(analysis.clauses_unverified, 1)
        self.assertEqual(analysis.matrix[0].equivalence_verdict, VERDICT_UNVERIFIED)

    def test_stronger_acceptance_criteria_remains_actionable(self):
        project, _successor, _evidence, _authority = self.prepare()
        self.attach_source(project, verified_successor=True)
        text = "Deliver the canonical audit artifact with wave3 producer."
        analysis = analyze_handoff_delta(project, text, stronger_acceptance=True)
        self.assertEqual(analysis.matrix[0].equivalence_verdict, VERDICT_CHANGED_CONTRACT)
        self.assertEqual(analysis.implementation_delta, 1)

    def test_different_project_lineage_refuses_equivalence(self):
        project, _successor, _evidence, _authority = self.prepare()
        self.attach_source(project, verified_successor=True)
        text = "Deliver the canonical audit artifact with wave3 producer."
        analysis = analyze_handoff_delta(
            project, text, candidate_lineage="foreign-lineage-12345678"
        )
        self.assertEqual(analysis.status, NEW_IMPLEMENTATION_REQUIRED)
        self.assertEqual(analysis.matrix[0].equivalence_verdict, VERDICT_MISSING)

    def test_operator_repeat_request_stays_actionable(self):
        project, _successor, _evidence, _authority = self.prepare()
        self.attach_source(project, verified_successor=True)
        text = "Deliver the canonical audit artifact with wave3 producer."
        analysis = analyze_handoff_delta(project, text, operator_repeat=True)
        self.assertEqual(analysis.status, NEW_IMPLEMENTATION_REQUIRED)
        self.assertEqual(analysis.matrix[0].equivalence_verdict, VERDICT_MISSING)

    def test_blocked_matching_work_does_not_assume_satisfaction(self):
        project, successor, _evidence, _authority = self.prepare()
        board_path = project / ".saipen" / "BOARD.md"
        board = board_path.read_text(encoding="utf-8")
        # Move the row into the section that already exists: a second
        # `## BLOCKED` heading is a board the shared parser refuses, and an
        # unreadable board answers "no candidate" instead of this question.
        lines = board.splitlines()
        row = next(line for line in lines if line.startswith("- [x] " + successor + " "))
        lines.remove(row)
        lines.insert(lines.index("## BLOCKED") + 1, row.replace("- [x] ", "- [/] ", 1))
        board_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        text = "Deliver the canonical audit artifact with wave3 producer."
        analysis = analyze_handoff_delta(project, text)
        self.assertEqual(analysis.status, EXISTING_IMPLEMENTATION_UNVERIFIED)
        self.assertEqual(analysis.matrix[0].equivalence_verdict, VERDICT_UNVERIFIED)

    def test_unauthorized_external_publication_retains_gate(self):
        project, _successor, _evidence, _authority = self.prepare()
        self.attach_source(project, verified_successor=True)
        text = "Publish the canonical audit artifact to external public registry."
        analysis = analyze_handoff_delta(project, text, requires_publication=True)
        self.assertEqual(analysis.status, INDEPENDENT_OPERATOR_GATE)
        self.assertEqual(analysis.authority_boundary, "PUBLICATION_GATE_REQUIRED")

    def test_source_with_unresolved_clause_cannot_settle_zero_delta(self):
        project, _successor, _evidence, _authority = self.prepare()
        receipt = self.attach_source(project, verified_successor=True)
        handoff = (
            "Handoff:\n\n"
            "1. Deliver the canonical audit artifact.\n"
            "2. Deploy to external staging.\n"
        )
        analysis = analyze_handoff_delta(project, handoff, source_receipt=receipt)
        settled = settle_proven_duplicate(project, analysis)
        self.assertFalse(settled["ok"], settled)
        self.assertEqual(settled["code"], "CANONICAL_SETTLEMENT_REFUSED")

    def test_compact_diagnostic_reporting_contract(self):
        project, _successor, _evidence, _authority = self.prepare()
        receipt = self.attach_source(project, verified_successor=True)
        text = "Deliver the canonical audit artifact with wave3 producer."
        analysis = analyze_handoff_delta(project, text, source_receipt=receipt)
        report = analysis.format_compact_report()
        self.assertIn("STATUS: EXISTING_IMPLEMENTATION_VERIFIED", report)
        self.assertIn(f"SOURCE_RECEIPT: {receipt}", report)
        self.assertIn("CLAUSES_TOTAL: 1", report)
        self.assertIn("CLAUSES_VERIFIED_EXISTING: 1", report)
        self.assertIn("IMPLEMENTATION_DELTA: 0", report)
        self.assertIn("SOURCE_SETTLEMENT: CANONICALLY_CLOSED", report)
        self.assertIn("WORK_SETTLEMENT: NO_DUPLICATE_WORK", report)
        self.assertIn("NEXT_EXACT_ACTION: CONTINUE_EXISTING_WORK", report)


HANDOFF = (
    "Handoff:\n\n"
    "1. Ensure the canonical audit artifact written by producer wave3 exists.\n"
    "2. Deliver the canonical audit artifact for the A3 Quick3 audit.\n"
)

PARTIAL_HANDOFF = (
    "Handoff:\n\n"
    "1. Ensure the canonical audit artifact written by producer wave3 exists.\n"
    "2. Deploy the service to external staging cluster.\n"
)


class StartPreAdmissionTests(AttachSourceMixin, SupersessionFixture):
    """START must classify a handoff before it becomes Work (SRC-323 §4, §6, §7)."""

    def test_start_settles_a_proven_duplicate_without_creating_work(self):
        project, successor, _evidence, _authority = self.prepare()
        self.attach_source(project, verified_successor=True)
        before = set(parse_board((project / ".saipen" / "BOARD.md").read_text())["tickets"])

        started = start_work(project, "tester", actor_source="explicit", text=HANDOFF)

        self.assertTrue(started["ok"], started)
        self.assertEqual(started["code"], "ALREADY_SATISFIED", started)
        self.assertFalse(started["work_created"], started)
        self.assertEqual(started["matched_existing_work"], [successor])
        self.assertEqual(started["implementation_delta"], 0)
        receipt = started["receipt"]
        after = set(parse_board((project / ".saipen" / "BOARD.md").read_text())["tickets"])
        self.assertEqual(after, before, "a satisfied handoff must not mint Work")
        self.assertTrue(intake.coverage_complete(project, receipt))
        self.assertIn("STATUS: EXISTING_IMPLEMENTATION_VERIFIED", started["report"])

    def test_start_projects_only_the_unresolved_clause(self):
        project, _successor, _evidence, _authority = self.prepare()
        self.attach_source(project, verified_successor=True)

        started = start_work(project, "tester", actor_source="explicit", text=PARTIAL_HANDOFF)

        self.assertTrue(started["ok"], started)
        self.assertIsNotNone(started["ticket"], started)
        receipt = started["receipt"]
        ledger = intake._read_coverage(project, receipt)
        self.assertEqual(ledger["requirements"][f"{receipt}:R001"]["disposition"], "VERIFIED")
        self.assertEqual(ledger["requirements"][f"{receipt}:R002"]["disposition"], "UNKNOWN")
        self.assertEqual(
            intake.coverage_summary(project, receipt)["unresolved"], [f"{receipt}:R002"]
        )


if __name__ == "__main__":
    unittest.main()
