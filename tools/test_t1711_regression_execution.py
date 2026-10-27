"""SRC-212: measured active regression evidence, not a caller's verdict."""

from __future__ import annotations

import importlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from saipen_engine import intake, operations
from saipen_engine.board import parse_board, set_ticket_field
from saipen_engine.oracle import parse_identity
from test_regression_gate import (
    GREEN,
    S1,
    S2,
    V1,
    RegressionGateFixture,
    _evidence,
)

try:
    EXECUTION = importlib.import_module("saipen_engine.regression_execution")
except ModuleNotFoundError:
    EXECUTION = None


class IdentityControls(unittest.TestCase):
    def test_contradictory_aliases_do_not_produce_an_identity(self):
        self.assertEqual(parse_identity("verifier:1111aaaa oracle:9999dddd subject:2222bbbb"), {})

    def test_equal_aliases_remain_compatible(self):
        self.assertEqual(
            parse_identity("verifier:1111aaaa oracle:1111aaaa subject:2222bbbb"),
            {"verifier": "1111aaaa", "subject": "2222bbbb"},
        )


class AttemptControls(RegressionGateFixture):
    def attempt(self, action, **kwargs):
        result = operations.attempt_lifecycle(self.project, "tester", action, **kwargs)
        self.assertTrue(result.ok, result.to_dict())

    def pair(self):
        self.record(_evidence("FAIL", V1, S1))
        self.record(_evidence("PASS", V1, S2))

    def refuse(self):
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_contradictory_identity_cannot_approve_review(self):
        self.record(_evidence("FAIL", V1, S1) + " oracle:9999dddd")
        self.record(_evidence("PASS", V1, S2))
        self.refuse()

    def test_halves_from_different_attempts_cannot_approve_review(self):
        self.attempt("open")
        self.record(_evidence("FAIL", V1, S1))
        self.attempt("close", result="failed", stop="validation_failure")
        self.attempt("open")
        self.record(_evidence("PASS", V1, S2))
        self.attempt("close", result="yielded", stop="deliberate_handoff")
        self.refuse()

    def test_a_new_attempt_invalidates_the_previous_attempt_pair(self):
        self.attempt("open")
        self.pair()
        self.attempt("close", result="candidate", stop="completed_execution")
        self.attempt("open")
        self.refuse()

    def test_an_attempt_and_absent_attempt_are_distinct(self):
        self.attempt("open")
        self.record(_evidence("FAIL", V1, S1))
        self.attempt("close", result="failed", stop="validation_failure")
        self.record(_evidence("PASS", V1, S2))
        self.refuse()

    def test_legacy_same_attempt_records_remain_valid(self):
        self.attempt("open")
        self.pair()
        self.assertTrue(self.to_review().ok)

    def test_legacy_absent_attempt_records_remain_valid(self):
        self.pair()
        self.assertTrue(self.to_review().ok)


CHECK = """import unittest
from subject import answer
class Control(unittest.TestCase):
    def test_answer(self): self.assertEqual(answer(), 2)
if __name__ == "__main__": unittest.main()
"""


class ExecutionControls(RegressionGateFixture):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.project.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
        )
        (self.project / "subject.py").write_text("def answer(): return 2\n", encoding="utf-8")
        (self.project / "check.py").write_text(CHECK, encoding="utf-8")
        evidence = self.project / ".saipen/evidence"
        evidence.mkdir(exist_ok=True)
        (evidence / "before.py").write_text("def answer(): return 1\n", encoding="utf-8")
        self.contract_path = evidence / "contract.json"
        self.contract = {
            "schema": 1,
            "command": ["{python}", "-B", "check.py"],
            "format": "unittest",
            "context": ["subject.py", "check.py"],
            "oracle_files": ["check.py"],
            "subject_files": ["subject.py"],
            "before": {"subject.py": ".saipen/evidence/before.py"},
            "timeout": 30,
        }
        self.write_contract()

    def write_contract(self):
        self.contract_path.write_text(json.dumps(self.contract), encoding="utf-8")

    def arm(self):
        options = {"regression": "required"}
        if "evidence_profile" in inspect.signature(operations.ticket_verify).parameters:
            options["evidence_profile"] = "executed"
        result = operations.ticket_verify(self.project, "T-7", "tester", None, **options)
        self.assertTrue(result.ok, result.to_dict())

    def execute(self, **kwargs):
        self.assertIsNotNone(EXECUTION, "supported active execution operation is absent")
        return EXECUTION.execute_pair(self.project, "T-7", "tester", self.contract_path, **kwargs)

    def assert_refused_without_canonical_writes(self, **kwargs):
        before = self.canonical_digest()
        result = self.execute(**kwargs)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(before, self.canonical_digest())
        return result

    def test_executed_profile_rejects_an_unknown_self_declared_digest(self):
        self.arm()
        self.record(_evidence("FAIL", "1234abcd", S1))
        self.record(_evidence("PASS", "1234abcd", S2))
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(before, self.canonical_digest())

    def test_executed_profile_without_a_genuine_pair_refuses(self):
        self.arm()
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(before, self.canonical_digest())

    def test_actual_active_pair_is_admitted_and_typed(self):
        result = self.execute()
        self.assertTrue(result.ok, result.to_dict())
        evidence = json.loads((self.project / result.data["record"]).read_text(encoding="utf-8"))
        self.assertEqual(evidence["evidence_class"], "executed")
        self.assertEqual(evidence["ticket"], "T-7")
        self.assertEqual(evidence["runs"][0]["exit_code"], 1)
        self.assertEqual(evidence["runs"][1]["exit_code"], 0)
        self.assertGreater(evidence["runs"][0]["ran"], 0)
        self.assertEqual(evidence["before"]["verifier"], evidence["after"]["verifier"])
        self.assertNotEqual(evidence["before"]["subject"], evidence["after"]["subject"])
        board = parse_board((self.project / ".saipen/BOARD.md").read_text(encoding="utf-8"))
        self.assertEqual(board["tickets"]["T-7"]["fields"]["regression_evidence"], "executed")
        self.assertTrue(self.to_review().ok)

    def test_source_clause_accepts_only_the_journal_bound_execution_record(self):
        captured = intake.capture(
            self.project,
            "The current answer passes check.py.",
            source_kind="user_instruction",
            work="T-7",
        )
        self.assertTrue(captured["ok"], captured)
        receipt = captured["receipt"]
        self.assertTrue(intake.ensure_request_clause(self.project, receipt)["ok"])
        added = intake.add_requirement(
            self.project, receipt, rid="R002",
            text="check.py asserts the answer equals 2", clause_class="requirement",
        )
        self.assertTrue(added["ok"], added)
        unrelated = intake.capture(
            self.project, "An independent request.",
            source_kind="user_instruction", work="T-7",
        )
        self.assertTrue(unrelated["ok"], unrelated)
        self.assertTrue(intake.ensure_request_clause(self.project, unrelated["receipt"])["ok"])
        board_path = self.project / ".saipen" / "BOARD.md"
        board = board_path.read_text(encoding="utf-8")
        ticket = parse_board(board)["tickets"]["T-7"]
        board_path.write_text(
            board.replace(
                ticket["raw"], set_ticket_field(ticket["raw"], "source_receipts", receipt)
            ),
            encoding="utf-8",
        )
        (self.project / "other.py").write_text("assert True\n", encoding="utf-8")
        ran = self.execute()
        self.assertTrue(ran.ok, ran.to_dict())
        carrier = ran.data["record"]

        wrong_source = intake.set_disposition(
            self.project, unrelated["receipt"], "R001", "VERIFIED",
            work="T-7", evidence=carrier,
            verification=f"python check.py -> PASS record: {carrier}",
        )
        self.assertEqual(wrong_source["code"], "EVIDENCE_UNRELATED", wrong_source)

        wrong_work = intake.set_disposition(
            self.project, receipt, "R001", "VERIFIED",
            work="T-999", evidence=carrier,
            verification=f"python check.py -> PASS record: {carrier}",
        )
        self.assertEqual(wrong_work["code"], "EVIDENCE_UNRELATED", wrong_work)
        wrong_oracle = intake.set_disposition(
            self.project, receipt, "R001", "VERIFIED",
            work="T-7", evidence=carrier,
            verification=f"python other.py -> PASS record: {carrier}",
        )
        self.assertEqual(wrong_oracle["code"], "EVIDENCE_UNRELATED", wrong_oracle)

        settled = intake.set_disposition(
            self.project,
            receipt,
            "R001",
            "VERIFIED",
            work="T-7",
            evidence=carrier,
            verification=f"python check.py -> PASS record: {carrier}",
        )
        self.assertTrue(settled["ok"], settled)
        second = intake.set_disposition(
            self.project, receipt, "R002", "VERIFIED", work="T-7",
            evidence=carrier,
            verification=f"python check.py -> PASS record: {carrier}",
        )
        self.assertTrue(second["ok"], second)
        self.assertEqual(intake.coverage_summary(self.project, receipt)["unresolved"], [])

    def test_exact_replay_produces_no_duplicate_authority(self):
        first = self.execute()
        self.assertTrue(first.ok, first.to_dict())
        before = self.canonical_digest()
        second = self.execute()
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual(second.data["record"], first.data["record"])
        self.assertEqual(self.canonical_digest(), before)

    def test_changed_receipt_cannot_approve_review(self):
        result = self.execute()
        self.assertTrue(result.ok, result.to_dict())
        target = self.project / result.data["record"]
        value = json.loads(target.read_text(encoding="utf-8"))
        value["ticket"] = "T-999"
        target.write_text(json.dumps(value), encoding="utf-8")
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_a_newer_failure_supersedes_the_receipt(self):
        result = self.execute()
        self.assertTrue(result.ok, result.to_dict())
        value = json.loads((self.project / result.data["record"]).read_text(encoding="utf-8"))
        self.record(_evidence("FAIL", value["before"]["verifier"], value["before"]["subject"]))
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_a_new_verify_boundary_cannot_reuse_old_execution(self):
        self.assertTrue(self.execute().ok)
        self.assertTrue(operations.transition_phase(self.project, "BUILD", "tester", "T-7").ok)
        self.assertTrue(operations.transition_phase(self.project, "VERIFY", "tester", "T-7").ok)
        self.record(GREEN)
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_a_new_attempt_cannot_reuse_old_execution(self):
        self.assertTrue(self.execute().ok)
        self.assertTrue(operations.attempt_lifecycle(self.project, "tester", "open").ok)
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_post_fix_byte_changes_invalidate_execution(self):
        self.assertTrue(self.execute().ok)
        (self.project / "subject.py").write_text("def answer(): return 3\n", encoding="utf-8")
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_oracle_byte_changes_invalidate_execution(self):
        self.assertTrue(self.execute().ok)
        (self.project / "check.py").write_text(CHECK + "# different check\n", encoding="utf-8")
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_invalid_contracts_cannot_be_results_or_escape_the_project(self):
        for key, value in (
            ("verifier", "1234abcd"),
            ("result", "PASS"),
            ("format", "unknown"),
            ("context", ["../outside.py"]),
            ("timeout", 0),
        ):
            with self.subTest(key=key):
                original = dict(self.contract)
                self.contract[key] = value
                self.write_contract()
                self.assert_refused_without_canonical_writes()
                self.contract = original
                self.write_contract()

    def test_identical_subjects_are_not_a_pair(self):
        (self.project / ".saipen/evidence/before.py").write_text(
            "def answer(): return 2\n", encoding="utf-8"
        )
        self.assert_refused_without_canonical_writes()

    def test_a_post_fix_failure_is_not_an_approval(self):
        (self.project / "subject.py").write_text("def answer(): return 3\n", encoding="utf-8")
        self.assert_refused_without_canonical_writes()

    def test_a_launch_error_or_zero_tests_is_not_regression_evidence(self):
        for code in ("raise RuntimeError('startup')\n", "import unittest; unittest.main()\n"):
            with self.subTest(code=code):
                (self.project / "check.py").write_text(code, encoding="utf-8")
                self.assert_refused_without_canonical_writes()

    def test_oracle_and_subject_cannot_overlap(self):
        self.contract["oracle_files"] = ["subject.py"]
        self.write_contract()
        self.assert_refused_without_canonical_writes()

    def test_timeout_is_a_structured_refusal_with_owned_cleanup(self):
        self.contract["command"] = ["{python}", "-c", "import time; time.sleep(30)"]
        self.contract["timeout"] = 1
        self.write_contract()
        result = self.assert_refused_without_canonical_writes()
        self.assertIn("TIMEOUT", result.message)

    def test_preserved_prior_input_changes_invalidate_execution(self):
        self.assertTrue(self.execute().ok)
        carrier = self.project / ".saipen/evidence/before.py"
        original = carrier.read_bytes()
        carrier.write_text("def answer(): return 99\n", encoding="utf-8")
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)
        carrier.write_bytes(original)
        self.assertTrue(self.to_review().ok)

    def test_changed_input_contract_cannot_spend_the_measured_pair(self):
        self.assertTrue(self.execute().ok)
        alternative = self.project / ".saipen/evidence/alternative.py"
        alternative.write_bytes((self.project / ".saipen/evidence/before.py").read_bytes())
        self.contract["before"]["subject.py"] = ".saipen/evidence/alternative.py"
        self.write_contract()
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_prior_material_changed_before_commit_refuses_without_canonical_writes(self):
        self.assertIsNotNone(EXECUTION)
        original = EXECUTION._binding
        calls = []

        def move_after_fresh_binding(*args, **kwargs):
            binding = original(*args, **kwargs)
            calls.append(binding)
            if len(calls) == 2:
                (self.project / ".saipen/evidence/before.py").write_text(
                    "def answer(): return 99\n", encoding="utf-8"
                )
            return binding

        with patch.object(EXECUTION, "_binding", move_after_fresh_binding):
            self.assert_refused_without_canonical_writes()

    def test_original_source_changed_by_a_verifier_cannot_be_admitted(self):
        original = repr(str(self.project / "subject.py"))
        (self.project / "check.py").write_text(
            "from pathlib import Path\n"
            + f"Path({original}).write_text('def answer(): return 99\\n')\n"
            + CHECK,
            encoding="utf-8",
        )
        self.assert_refused_without_canonical_writes()

    def test_environment_changes_invalidate_the_configured_verifier(self):
        self.assertTrue(self.execute().ok)
        with patch.dict(os.environ, {"REGRESSION_CONTROL_ENV": "changed"}):
            before = self.canonical_digest()
            self.assertFalse(self.to_review().ok)
            self.assertEqual(self.canonical_digest(), before)

    def test_a_completed_producing_attempt_keeps_its_genuine_pair(self):
        self.assertTrue(operations.attempt_lifecycle(self.project, "tester", "open").ok)
        result = self.execute()
        self.assertTrue(result.ok, result.to_dict())
        self.assertTrue(
            operations.attempt_lifecycle(
                self.project, "tester", "close", result="candidate", stop="completed_execution"
            ).ok
        )
        self.assertTrue(self.to_review().ok)

    def test_a_changed_acceptance_contract_cannot_spend_old_execution(self):
        self.assertTrue(self.execute().ok)
        self.assertTrue(
            operations.ticket_verify(
                self.project,
                "T-7",
                "tester",
                "A newly required and different verification contract",
            ).ok
        )
        self.record(GREEN)
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_the_successful_execution_does_not_replace_ordinary_verification(self):
        self.record("verify -> FAIL: another mandatory gate failed")
        self.assertTrue(self.execute().ok)
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_forged_checkpoint_halves_cannot_replace_a_measured_pair(self):
        result = self.execute()
        self.assertTrue(result.ok, result.to_dict())
        value = json.loads((self.project / result.data["record"]).read_text(encoding="utf-8"))
        self.record(_evidence("FAIL", value["before"]["verifier"], value["before"]["subject"]))
        self.record(_evidence("PASS", value["after"]["verifier"], value["after"]["subject"]))
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_a_fresh_measured_pair_after_a_newer_failure_restores_admission(self):
        first = self.execute()
        self.assertTrue(first.ok, first.to_dict())
        value = json.loads((self.project / first.data["record"]).read_text(encoding="utf-8"))
        self.record(_evidence("FAIL", value["before"]["verifier"], value["before"]["subject"]))
        second = self.execute()
        self.assertTrue(second.ok, second.to_dict())
        self.assertNotEqual(first.data["record"], second.data["record"])
        self.assertTrue(self.to_review().ok)

    def native(self, words, *, env=None):
        self.assertIsNotNone(EXECUTION)
        command = [
            sys.executable,
            "-B",
            str(Path(EXECUTION.__file__).resolve().parents[1] / "saipen.py"),
            "--project-root",
            str(self.project),
            "--agent",
            "tester",
            *words,
            "--json",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            env=env,
        )
        return result, json.loads(result.stdout)

    def test_native_cli_admits_the_actual_active_pair(self):
        result, value = self.native(
            ["work", "regression", "T-7", "--file", str(self.contract_path)]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(value["ok"], value)
        self.assertEqual(value["evidence_class"], "executed")

    def test_native_cli_dry_run_is_write_free(self):
        before = self.canonical_digest()
        result, value = self.native(
            ["work", "regression", "T-7", "--file", str(self.contract_path), "--dry-run"]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(value["ok"], value)
        self.assertEqual(self.canonical_digest(), before)

    def test_native_cli_can_require_executed_evidence_without_changing_verify(self):
        original = parse_board((self.project / ".saipen/BOARD.md").read_text(encoding="utf-8"))
        result, value = self.native(
            ["ticket", "regression", "T-7", "required", "--evidence", "executed"]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(value["ok"], value)
        changed = parse_board((self.project / ".saipen/BOARD.md").read_text(encoding="utf-8"))
        self.assertEqual(changed["tickets"]["T-7"]["fields"]["regression_evidence"], "executed")
        self.assertEqual(
            changed["tickets"]["T-7"]["fields"]["verify"],
            original["tickets"]["T-7"]["fields"]["verify"],
        )

    def test_dry_run_executes_nothing_and_writes_no_project_bytes(self):
        (self.project / "check.py").write_text(
            "from pathlib import Path; Path('UNSAFE').write_text('ran')\n", encoding="utf-8"
        )
        before = self.canonical_digest()
        result = self.execute(dry_run=True)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(self.canonical_digest(), before)
        self.assertFalse((self.project / "UNSAFE").exists())
        self.assertNotIn("record", result.data)

    def test_read_only_refuses_before_execution(self):
        with patch.dict(os.environ, {"SAIPEN_CAPABILITY": "read-only"}):
            result = self.assert_refused_without_canonical_writes()
        self.assertEqual(result.code, "CAPABILITY_READ_ONLY")

    def test_a_foreign_executor_cannot_measure_or_admit_this_work(self):
        self.assertIsNotNone(EXECUTION)
        before = self.canonical_digest()
        result = EXECUTION.execute_pair(self.project, "T-7", "other", self.contract_path)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.canonical_digest(), before)

    def test_unrequired_work_preserves_the_existing_flow(self):
        fixture = RegressionGateFixture(methodName="runTest")
        fixture.REGRESSION = ""
        try:
            fixture.setUp()
            self.assertTrue(fixture.to_review().ok)
        finally:
            fixture.doCleanups()

    @unittest.skipUnless(shutil.which("node"), "native Node is unavailable")
    def test_consumer_compatible_javascript_pair_uses_the_same_active_contract(self):
        (self.project / "subject.cjs").write_text("exports.answer = () => 2;\n", encoding="utf-8")
        (self.project / ".saipen/evidence/before.cjs").write_text(
            "exports.answer = () => 1;\n", encoding="utf-8"
        )
        (self.project / "check.cjs").write_text(
            "const test = require('node:test'); const assert = require('node:assert/strict');\n"
            "const {answer} = require('./subject.cjs');\n"
            "test('clipboard result contract', () => assert.equal(answer(), 2));\n",
            encoding="utf-8",
        )
        self.contract.update(
            command=[shutil.which("node"), "--test", "--test-reporter=tap", "check.cjs"],
            format="tap",
            context=["subject.cjs", "check.cjs"],
            oracle_files=["check.cjs"],
            subject_files=["subject.cjs"],
            before={"subject.cjs": ".saipen/evidence/before.cjs"},
        )
        self.write_contract()
        result = self.execute()
        self.assertTrue(result.ok, result.to_dict())
        self.assertTrue(self.to_review().ok)


if __name__ == "__main__":
    unittest.main()
