"""Native acceptance must enforce the complete hash-bound compacted contract."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import operations as ops  # noqa: E402
from saipen_engine.board import parse_board, set_ticket_field  # noqa: E402
from saipen_engine.journal import semantic_receipts_for_operation  # noqa: E402
from saipen_engine.plan import semantic_payload_hash  # noqa: E402
import test_t1718_acceptance_contract as support  # noqa: E402
from test_t1718_acceptance_contract import ContractFixture, sha, tree  # noqa: E402


def contract(count=9, *, witness="UNIT", width=135):
    return "; ".join(
        f"AC-{number:02d} [{witness}] outcome {number} " + "x" * width
        for number in range(1, count + 1)
    )


def contracts(root):
    return sorted(semantic_receipts_for_operation(root, "ticket_verify"),
                  key=lambda record: record["receipt_metadata"]["acceptance_contract"]["event"])


class CompactionFixture(ContractFixture):
    def ticket(self):
        return parse_board((self.project / ".saipen/BOARD.md").read_text(encoding="utf-8"))[
            "tickets"
        ]["T-7"]

    def passes(self, count=9):
        for number in range(1, count + 1):
            self.record(
                f"AC-EVIDENCE AC-{number:02d} PASS behavioral witness=UNIT surface=fixture"
            )

    def later_compaction(self):
        # Disposable historical fixture: an oversized unrelated field forces
        # the real canonical recovery writer to compact an existing contract.
        path = self.project / ".saipen/BOARD.md"
        text = path.read_text(encoding="utf-8")
        raw = self.ticket()["raw"]
        path.write_text(text.replace(raw, set_ticket_field(
            raw, "recurrence", "history " * 200, enforce_cap=False)),
                        encoding="utf-8")
        result = ops.compact_board(self.project, "T-7", "tester")
        self.assertTrue(result.ok, result.to_dict())

    def cli(self):
        return subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), "acceptance", "T-7",
             "--project-root", str(self.project), "--json"],
            cwd=TOOLS.parent, capture_output=True, text=True, encoding="utf-8", check=False,
        )

    def legacy_declare(self, declared):
        # Reproduce the old canonical writer on a disposable fixture: the
        # complete row is preserved, but journal metadata records its bounded
        # projection. Never rewrite an already committed receipt.
        apply = ops.apply_plan
        original = self.ticket()["fields"]["verify"]

        def old_writer(root, plan):
            board = next(target for target in plan.targets if target.role == "board")
            projected = parse_board(board.content.decode("utf-8"))["tickets"]["T-7"][
                "fields"
            ]["verify"]
            metadata = {"acceptance_contract": {
                **plan.receipt_metadata["acceptance_contract"],
                "original": original, "original_sha256": sha(original),
                "replacement": projected, "replacement_sha256": sha(projected),
            }}
            request = {**plan.semantic_request, **metadata}
            return apply(root, replace(plan, semantic_request=request,
                                       semantic_payload_hash=semantic_payload_hash(request),
                                       receipt_metadata=metadata))

        with patch.object(ops, "apply_plan", side_effect=old_writer):
            self.declare(declared)


class NativeCompactionRegressionTests(CompactionFixture):
    def test_initial_oversized_declaration_journals_all_outcomes(self):
        declared = contract()
        self.declare(declared)
        self.assertIn("detail_ref", self.ticket()["fields"])
        records = contracts(self.project)
        saved = records[-1]["receipt_metadata"]["acceptance_contract"]
        self.assertEqual(saved["replacement"], declared)
        self.assertEqual(saved["replacement_sha256"], sha(declared))

    def test_every_preserved_outcome_is_required_by_native_review(self):
        self.declare(contract())
        self.passes(8)
        before = tree(self.project)
        result = self.to_review()
        self.assertFalse(result.ok, result.to_dict())
        self.assertIn("AC-09", result.message)
        self.assertEqual(tree(self.project), before)

    def test_complete_contract_remains_finishable_after_later_compaction(self):
        self.declare(contract())
        self.later_compaction()
        self.passes()
        result = self.finish()
        self.assertTrue(result.ok, result.to_dict())

    def test_same_full_contract_can_be_reissued_without_amendment(self):
        declared = contract()
        self.declare(declared)
        result = ops.ticket_verify(self.project, "T-7", "tester", declared)
        self.assertTrue(result.ok, result.to_dict())
        saved = contracts(self.project)[-1][
            "receipt_metadata"
        ]["acceptance_contract"]
        self.assertEqual((saved["original"], saved["replacement"]), (declared, declared))

    def test_short_journal_survives_later_compaction(self):
        self.declare(contract(3, width=10))
        self.later_compaction()
        self.passes(3)
        result = self.finish()
        self.assertTrue(result.ok, result.to_dict())

    def test_public_acceptance_reports_every_preserved_outcome_read_only(self):
        self.declare(contract())
        self.passes(8)
        before = tree(self.project)
        proc = self.cli()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["declared"], 9)
        self.assertEqual(result["criteria"][-1]["state"], "UNVERIFIED")
        self.assertEqual(result["undeclared_evidence"], [])
        self.assertEqual(tree(self.project), before)


class CompactedAuthorityTests(CompactionFixture):
    def test_hidden_all_criteria_cannot_bypass_the_contract_writer(self):
        declared = "preamble " * 45 + "; " + contract()
        self.declare(declared)
        self.assertFalse(any(part.strip().startswith("AC-")
                             for part in self.ticket()["fields"]["verify"].split(";")))
        before = tree(self.project)
        result = ops.ticket_verify(self.project, "T-7", "tester", "only fixtures")
        self.assertFalse(result.ok, result.to_dict())
        self.assertIn("amendment", result.message)
        self.assertEqual(tree(self.project), before)
        result = ops.ticket_verify(self.project, "T-7", "tester", declared)
        self.assertTrue(result.ok, result.to_dict())

    def test_literal_detail_text_is_preserved_as_an_outcome(self):
        declared = "AC-01 [UNIT] report [detail_ref: not a pointer] literally"
        self.declare(declared)
        self.passes(1)
        result = self.finish()
        self.assertTrue(result.ok, result.to_dict())

    def test_missing_detail_head_cannot_admit_a_legacy_short_contract(self):
        self.legacy_declare(contract())
        path = self.project / ".saipen/BOARD.md"
        text = path.read_text(encoding="utf-8")
        raw = self.ticket()["raw"]
        reference = self.ticket()["fields"]["detail_ref"]
        path.write_text(text.replace(raw, raw.replace(" | detail_ref: " + reference, "")),
                        encoding="utf-8")
        self.assertNotIn("detail_ref", self.ticket()["fields"])
        before = tree(self.project)
        self.assertFalse(ops.ticket_verify(self.project, "T-7", "tester", "only fixtures").ok)
        self.assertFalse(self.to_review().ok)
        self.assertEqual(tree(self.project), before)

    def test_each_preserved_criterion_is_enforced_at_review_and_finish(self):
        for missing in range(1, 10):
            with self.subTest(missing=missing):
                fixture = CompactionFixture()
                fixture.setUp()
                try:
                    fixture.declare(contract())
                    for number in range(1, 10):
                        if number != missing:
                            fixture.record(
                                f"AC-EVIDENCE AC-{number:02d} PASS behavioral "
                                "witness=UNIT surface=fixture"
                            )
                    before = tree(fixture.project)
                    result = fixture.to_review()
                    self.assertFalse(result.ok, result.to_dict())
                    self.assertIn(f"AC-{missing:02d}", result.message)
                    self.assertEqual(tree(fixture.project), before)
                    fixture.record(f"AC-EVIDENCE AC-{missing:02d} PASS behavioral "
                                   "witness=UNIT surface=fixture")
                    self.assertTrue(fixture.to_review().ok)
                    self.assertTrue(ops.transition_phase(
                        fixture.project, "SHIP", "tester", "T-7").ok)
                    fixture.record(f"AC-EVIDENCE AC-{missing:02d} FAIL behavioral "
                                   "witness=UNIT surface=fixture")
                    before = tree(fixture.project)
                    result = ops.finish_ticket(fixture.project, "T-7", "tester")
                    self.assertFalse(result.ok, result.to_dict())
                    self.assertIn(f"AC-{missing:02d}", result.message)
                    self.assertEqual(tree(fixture.project), before)
                finally:
                    fixture.doCleanups()

    def test_removing_last_outcome_or_weakening_witness_still_requires_authority(self):
        declared = contract(witness="LIVE")
        self.declare(declared)
        for replacement in ("; ".join(declared.split("; ")[:-1]),
                            declared.replace("[LIVE]", "[UNIT]"), "only fixtures"):
            with self.subTest(replacement=replacement[-60:]):
                before = tree(self.project)
                result = ops.ticket_verify(self.project, "T-7", "tester", replacement)
                self.assertFalse(result.ok, result.to_dict())
                self.assertIn("amendment", result.message)
                self.assertEqual(tree(self.project), before)

    def test_finish_rechecks_all_criteria_after_review(self):
        self.declare(contract())
        self.passes()
        self.assertTrue(self.to_review().ok)
        self.assertTrue(ops.transition_phase(self.project, "SHIP", "tester", "T-7").ok)
        self.record("AC-EVIDENCE AC-09 FAIL behavioral witness=UNIT surface=fixture")
        before = tree(self.project)
        result = ops.finish_ticket(self.project, "T-7", "tester")
        self.assertFalse(result.ok, result.to_dict())
        self.assertIn("AC-09", result.message)
        self.assertEqual(tree(self.project), before)

    def test_corrupt_original_detail_refuses_writer_review_and_public_projection(self):
        self.declare(contract())
        self.passes()
        metadata = json.loads((self.project / self.ticket()["fields"]["detail_ref"]).read_text())
        original = self.project / metadata["original_record_path"]
        original.write_bytes(original.read_bytes() + b"tampered")
        before = tree(self.project)
        self.assertFalse(ops.ticket_verify(self.project, "T-7", "tester", contract()).ok)
        self.assertFalse(self.to_review().ok)
        proc = self.cli()
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(tree(self.project), before)

    def test_foreign_lineage_detail_refuses_public_projection(self):
        self.declare(contract())
        path = self.project / self.ticket()["fields"]["detail_ref"]
        metadata = json.loads(path.read_text())
        metadata["project_lineage"] = "lineage-" + "0" * 32
        path.write_text(json.dumps(metadata), encoding="utf-8")
        before = tree(self.project)
        proc = self.cli()
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("lineage", proc.stdout)
        self.assertEqual(tree(self.project), before)

    def test_inline_change_cannot_hide_a_stale_projection_behind_valid_detail(self):
        self.declare(contract())
        path = self.project / ".saipen/BOARD.md"
        text = path.read_text(encoding="utf-8")
        raw = self.ticket()["raw"]
        current = self.ticket()["fields"]["verify"]
        path.write_text(text.replace(raw, set_ticket_field(raw, "verify", current + " changed")),
                        encoding="utf-8")
        before = tree(self.project)
        self.assertFalse(self.to_review().ok)
        self.assertFalse(ops.ticket_verify(self.project, "T-7", "tester", contract()).ok)
        self.assertEqual(tree(self.project), before)

    def test_detail_bytes_are_bound_between_review_admission_and_apply(self):
        self.declare(contract())
        self.passes()
        before = self.canonical_digest()
        metadata = json.loads((self.project / self.ticket()["fields"]["detail_ref"]).read_text())
        apply = ops.apply_plan

        def changed(root, plan):
            path = root / metadata["original_record_path"]
            path.write_bytes(path.read_bytes() + b"changed after admission")
            return apply(root, plan)

        with patch.object(ops, "apply_plan", side_effect=changed):
            result = self.to_review()
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "STALE_STATE")
        self.assertEqual(self.canonical_digest(), before)


class PreservedLegacyTests(CompactionFixture):
    def test_a_needed_projection_outside_acquired_ancestry_still_refuses(self):
        from saipen_engine import board_compaction

        self.legacy_declare(contract())
        for _ in range(3):
            self.later_compaction()
        gather = board_compaction.gather_lineage

        def bounded(root, head, work):
            return gather(root, head, work, _limit=2)

        before = tree(self.project)
        with patch.object(board_compaction, "gather_lineage", side_effect=bounded):
            self.assertFalse(self.to_review().ok)
            self.assertFalse(ops.ticket_verify(self.project, "T-7", "tester", contract()).ok)
        self.assertEqual(tree(self.project), before)

    def test_initial_legacy_projection_enforces_the_last_preserved_criterion(self):
        self.legacy_declare(contract())
        self.passes(8)
        before = tree(self.project)
        result = self.to_review()
        self.assertFalse(result.ok, result.to_dict())
        self.assertIn("AC-09", result.message)
        self.assertEqual(tree(self.project), before)

    def test_initial_legacy_projection_finishes_without_rewriting_its_receipt(self):
        self.legacy_declare(contract())
        history = contracts(self.project)
        self.later_compaction()
        self.passes()
        result = self.finish()
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(contracts(self.project), history)

    def test_legacy_projection_allows_exact_full_contract_reissue(self):
        declared = contract()
        self.legacy_declare(declared)
        history = contracts(self.project)
        result = ops.ticket_verify(self.project, "T-7", "tester", declared)
        self.assertTrue(result.ok, result.to_dict())
        current = contracts(self.project)
        self.assertEqual(current[:-1], history)
        self.assertEqual(current[-1]["receipt_metadata"]["acceptance_contract"]["original"],
                         declared)

    def test_flattened_ancestry_keeps_full_acceptance_enforceable(self):
        from saipen_engine import board_compaction

        self.legacy_declare(contract())
        with patch.object(board_compaction, "_CHECKPOINT_TRIGGER", 2):
            for _ in range(4):
                self.later_compaction()
        head = self.ticket()["fields"]["detail_ref"]
        self.assertTrue(json.loads((self.project / head).read_text())["supersedes_checkpoint"])
        self.passes()
        result = self.finish()
        self.assertTrue(result.ok, result.to_dict())


class CompactedSupersessionTests(support.SupersessionTests):
    def test_compacted_old_and_successor_preserve_the_full_outcome(self):
        successor, evidence, authority = self.prepare_successor()
        # Existing native supersession already proves both admissions and LIVE
        # observations. Externalize both historical rows without changing any
        # outcome or journal, then use that same public supersession operation.
        path = self.project / ".saipen/BOARD.md"
        for work in ("T-7", successor):
            text = path.read_text(encoding="utf-8")
            row = parse_board(text)["tickets"][work]["raw"]
            path.write_text(text.replace(row, set_ticket_field(
                row, "recurrence", "history " * 200, enforce_cap=False)), encoding="utf-8")
            result = ops.compact_board(self.project, work, "tester")
            self.assertTrue(result.ok, result.to_dict())
        result = ops.supersede_ticket(self.project, "T-7", successor, "tester",
                                      evidence=evidence, authority=authority)
        self.assertTrue(result.ok, result.to_dict())


if __name__ == "__main__":
    unittest.main()
