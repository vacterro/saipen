"""SRC-225: real focused checks and bounded post-closure diagnostics."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from saipen_engine import closed_contracts, debt, intake
from saipen_engine.board import parse_board
from saipen_engine.journal import ensure_project_lineage, hash_bytes, run_mutation
from saipen_engine.paths import project_identity, unbound_environment
from test_work_reverify_cli import _make_project


class ClosedContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-closed-contracts-")
        self.addCleanup(self.temporary.cleanup)
        self.root = _make_project(Path(self.temporary.name))
        self.evidence = self.root / ".saipen/evidence"
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.contract = self.evidence / "focused.json"
        self.subject = self.root / "subject.py"
        self.oracle = self.root / "test_contract.py"
        self.subject.write_text("def value():\n    return 7\n", encoding="utf-8")
        self.oracle.write_text(
            "import unittest\nimport subject\n"
            "class Contract(unittest.TestCase):\n"
            "    def test_value(self):\n        self.assertEqual(subject.value(), 7)\n",
            encoding="utf-8",
        )
        self.configuration = {
            "schema": 1, "command": ["{python}", "-B", "-m", "unittest", "test_contract"],
            "format": "unittest", "context": ["subject.py", "test_contract.py"],
            "oracle_files": ["test_contract.py"], "subject_files": ["subject.py"], "timeout": 20,
        }
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.environment = patch.dict(os.environ, unbound_environment(), clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.capture = patch.object(debt, "capture_findings", return_value={
            "ok": True, "exit_code": 0, "gate": "core", "problems": [], "warnings": [],
        })
        self.capture.start()
        self.addCleanup(self.capture.stop)

    def recheck(self, **kwargs):
        return debt.reverify_work(self.root, "T-001", "tester",
                                  contract_path=self.contract, **kwargs)

    def observation(self):
        result = closed_contracts.inspect(self.root, "T-001")
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["rows"]), 1, result)
        return result["rows"][0]

    def test_real_regression_preserves_historical_receipt_and_done(self):
        before_board = (self.root / ".saipen/BOARD.md").read_bytes()
        before_log = (self.root / ".saipen/LOG.md").read_bytes()
        baseline = self.recheck()
        self.assertEqual(baseline["closed_contract"]["status"], "CURRENT_PASS", baseline)
        receipt = self.root / debt.REVERIFY_DIR / (baseline["receipt_id"] + ".json")
        original = receipt.read_bytes()
        self.subject.write_text("def value():\n    return 99\n", encoding="utf-8")
        self.assertEqual(self.observation()["status"], "REGRESSION_SUSPECT")
        failed = self.recheck()
        self.assertEqual(failed["closed_contract"]["status"], "CURRENT_REGRESSION", failed)
        self.assertEqual(failed["verdict"], "FAIL")
        self.assertEqual(self.observation()["status"], "CURRENT_REGRESSION")
        self.assertEqual(receipt.read_bytes(), original)
        self.assertEqual((self.root / ".saipen/BOARD.md").read_bytes(), before_board)
        self.assertEqual((self.root / ".saipen/LOG.md").read_bytes(), before_log)

    def test_new_declared_directory_member_invalidates_currentness_before_recheck(self):
        package = self.root / "subject"
        package.mkdir()
        self.configuration["context"].append("subject")
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        baseline = self.recheck()
        self.assertEqual(baseline["closed_contract"]["status"], "CURRENT_PASS", baseline)
        receipt = self.root / baseline["record"]
        original = receipt.read_bytes()
        (package / "__init__.py").write_text("def value(): return 99\n", encoding="utf-8")
        observation = self.observation()
        self.assertEqual(observation["status"], "REGRESSION_SUSPECT", observation)
        self.assertIn("subject/__init__.py", observation["changed_paths"])
        self.assertEqual(self.recheck()["closed_contract"]["status"], "CURRENT_REGRESSION")
        self.assertEqual(receipt.read_bytes(), original)

    def test_new_explicit_cache_member_is_in_the_declared_dependency_scope(self):
        directory = self.root / "__pycache__"
        directory.mkdir()
        self.configuration["context"].append("__pycache__")
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.assertEqual(self.recheck()["closed_contract"]["status"], "CURRENT_PASS")
        (directory / "required.txt").write_text("new declared input\n", encoding="utf-8")
        observation = self.observation()
        self.assertEqual(observation["status"], "REGRESSION_SUSPECT", observation)
        self.assertIn("__pycache__/required.txt", observation["changed_paths"])
        self.assertEqual(self.recheck()["closed_contract"]["status"], "CURRENT_PASS")

    def test_directory_membership_enumeration_respects_the_shared_path_budget(self):
        directory = self.root / "selected"
        directory.mkdir()
        self.configuration["context"].append("selected")
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.assertEqual(self.recheck()["closed_contract"]["status"], "CURRENT_PASS")
        for index in range(8):
            (directory / f"new-{index}.txt").write_text("new input\n", encoding="utf-8")
        with patch.object(closed_contracts, "MAX_PATHS", 3):
            result = closed_contracts.inspect(self.root, "T-001")
        self.assertFalse(result["ok"], result)
        self.assertIn("path limit", " ".join(result["errors"]))
        self.assertFalse(result["blocks_unrelated_work"])

    def test_removed_dependency_runs_the_unchanged_verifier_and_fails(self):
        dependency = self.root / "dependency.py"
        dependency.write_text("VALUE = 7\n", encoding="utf-8")
        self.subject.write_text("from dependency import VALUE\ndef value(): return VALUE\n",
                                encoding="utf-8")
        self.configuration["context"].append("dependency.py")
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.assertEqual(self.recheck()["closed_contract"]["status"], "CURRENT_PASS")
        dependency.unlink()
        failed = self.recheck()
        self.assertEqual(failed["closed_contract"]["status"], "CURRENT_REGRESSION", failed)

    def test_deleted_or_weakened_oracle_is_never_a_pass_even_on_retry(self):
        self.recheck()
        self.oracle.write_text("import unittest\nclass Test(unittest.TestCase):\n"
                               "    def test_nothing(self): self.assertTrue(True)\n",
                               encoding="utf-8")
        for _ in range(2):
            result = self.recheck()
            self.assertEqual(result["closed_contract"]["status"], "UNVERIFIED", result)
            self.assertEqual(result["verdict"], "FAIL")
        self.oracle.unlink()
        self.assertEqual(self.recheck()["closed_contract"]["status"], "UNVERIFIED")

    def test_changed_or_missing_oracle_is_unverified_without_executing_it(self):
        self.recheck()
        before_board = (self.root / ".saipen/BOARD.md").read_bytes()
        with patch.object(closed_contracts.execution, "_measure") as run:
            for content in ("# removed behavioral assertions\n", None):
                if content is None:
                    self.oracle.unlink()
                else:
                    self.oracle.write_text(content, encoding="utf-8")
                with self.subTest(content=content):
                    row = self.observation()
                    self.assertEqual(row["status"], "UNVERIFIED", row)
                    self.assertEqual(row["reason"], "ORACLE_CHANGED", row)
                    self.assertIn("test_contract.py", row["changed_paths"])
            run.assert_not_called()
        self.assertEqual((self.root / ".saipen/BOARD.md").read_bytes(), before_board)

    def test_formatting_and_refactor_are_suspects_until_focused_pass(self):
        self.recheck()
        for subject in ("\n# formatting\ndef value():\n    return 7\n",
                        "def value():\n    values = [3, 4]\n    return sum(values)\n"):
            self.subject.write_text(subject, encoding="utf-8")
            self.assertEqual(self.observation()["status"], "REGRESSION_SUSPECT")
            result = self.recheck()
            self.assertEqual(result["closed_contract"]["status"], "CURRENT_PASS", result)
            self.assertEqual(self.observation()["status"], "CURRENT_PASS")

    def test_zero_collection_and_runtime_failure_are_unverified(self):
        self.oracle.write_text("# no tests\n", encoding="utf-8")
        self.assertEqual(self.recheck()["closed_contract"]["status"], "UNVERIFIED")
        self.configuration["command"][0] = "saipen-nonexistent-test-runtime"
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.assertEqual(self.recheck()["closed_contract"]["status"], "UNVERIFIED")

    def test_first_failure_does_not_invent_historical_regression(self):
        self.subject.write_text("def value(): return 99\n", encoding="utf-8")
        result = self.recheck()
        self.assertEqual(result["closed_contract"]["status"], "CURRENT_CHECK_FAILED", result)

    def test_timeout_is_unverified_and_never_a_regression_verdict(self):
        self.configuration["timeout"] = 1
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.oracle.write_text("import time\ntime.sleep(3)\n", encoding="utf-8")
        result = self.recheck()
        self.assertEqual(result["closed_contract"]["status"], "UNVERIFIED", result)

    def test_unrelated_edit_does_not_invalidate_focused_observation(self):
        self.recheck()
        (self.root / "unrelated.txt").write_text("independent Work\n", encoding="utf-8")
        self.assertEqual(self.observation()["status"], "CURRENT_PASS")

    def test_implicit_cache_changes_do_not_invalidate_focused_proof(self):
        cache = self.root / "runtime/__pycache__"
        cache.mkdir(parents=True)
        artifact = cache / "subject.cpython-311.pyc"
        artifact.write_bytes(b"derived cache")
        self.configuration["context"].append("runtime")
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.recheck()
        artifact.unlink()
        pytest_cache = self.root / "runtime/.pytest_cache"
        pytest_cache.mkdir()
        (pytest_cache / "nodeids").write_text("new test session\n", encoding="utf-8")
        self.assertEqual(self.observation()["status"], "CURRENT_PASS")
        self.subject.write_text("def value(): return 99\n", encoding="utf-8")
        self.assertEqual(self.recheck()["closed_contract"]["status"], "CURRENT_REGRESSION")

    def test_explicit_cache_file_remains_a_bound_dependency(self):
        cache = self.root / "runtime/__pycache__"
        cache.mkdir(parents=True)
        artifact = cache / "required.pyc"
        artifact.write_bytes(b"explicit input")
        self.configuration["context"].append("runtime/__pycache__/required.pyc")
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.recheck()
        artifact.unlink()
        row = self.observation()
        self.assertEqual(row["status"], "REGRESSION_SUSPECT")
        self.assertIn("runtime/__pycache__/required.pyc", row["changed_paths"])

    def test_explicit_cache_directory_remains_a_bound_dependency(self):
        cache = self.root / "runtime/__pycache__"
        cache.mkdir(parents=True)
        artifact = cache / "required.pyc"
        artifact.write_bytes(b"explicit directory input")
        self.configuration["context"].append("runtime/__pycache__")
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.recheck()
        artifact.unlink()
        self.assertEqual(self.observation()["status"], "REGRESSION_SUSPECT")

    def test_explicit_subject_inside_cache_remains_in_directory_context(self):
        cache = self.root / "runtime/__pycache__"
        cache.mkdir(parents=True)
        artifact = cache / "required.pyc"
        artifact.write_bytes(b"explicit subject")
        self.configuration["context"].append("runtime")
        self.configuration["subject_files"].append("runtime/__pycache__/required.pyc")
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.assertEqual(self.recheck()["closed_contract"]["status"], "CURRENT_PASS")
        artifact.unlink()
        self.assertEqual(self.observation()["status"], "REGRESSION_SUSPECT")

    def test_same_inputs_reuse_one_immutable_observation(self):
        first = self.recheck()
        again = self.recheck()
        self.assertEqual(first["receipt_id"], again["receipt_id"], again)
        self.assertEqual(again["closed_contract"]["status"], "CURRENT_PASS")
        self.assertNotIn("dependencies", first["closed_contract"])
        self.assertGreater(first["closed_contract"]["dependency_count"], 0)
        self.assertIn("dependencies", json.loads((self.root / first["record"]).read_text(
            encoding="utf-8"))["closed_contract"])

    def test_generic_strict_pass_cannot_hide_a_confirmed_focused_failure(self):
        self.recheck()
        self.subject.write_text("def value(): return 99\n", encoding="utf-8")
        self.recheck()
        generic = debt.reverify_work(self.root, "T-001", "tester", derive_default=True)
        self.assertEqual(generic["verdict"], "FAIL", generic)
        self.assertIsNone(debt.current_tree_reverify(self.root, "T-001"))

    def test_changed_focused_inputs_need_remeasurement_for_closure(self):
        self.recheck()
        self.subject.write_text("def value(): return 99\n", encoding="utf-8")
        debt.reverify_work(self.root, "T-001", "tester", derive_default=True)
        self.assertIsNone(debt.current_tree_reverify(self.root, "T-001"))

    def test_unrelated_tree_change_preserves_executed_dependency_proof(self):
        self.recheck()
        with patch.object(debt, "_source_identity", return_value={
            "source_head": "different-unrelated-head", "source_tree_fingerprint": "unrelated-delta",
        }):
            receipt = debt.current_tree_reverify(self.root, "T-001")
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["currentness_basis"], "focused_dependencies")

    def test_changed_environment_invalidates_scoped_currentness(self):
        self.recheck()
        with patch.dict(os.environ, {"CLOSED_CONTRACT_RUNTIME_CONTROL": "changed"}):
            self.assertEqual(self.observation()["status"], "UNVERIFIED")
            self.assertIsNone(debt.current_tree_reverify(self.root, "T-001"))

    def test_explicit_remeasurement_refreshes_environment_and_preserves_history(self):
        first = self.recheck()
        receipt = self.root / first["record"]
        original = receipt.read_bytes()
        with patch.dict(os.environ, {"CLOSED_CONTRACT_RUNTIME_CONTROL": "changed"}):
            self.assertEqual(self.observation()["status"], "UNVERIFIED")
            refreshed = self.recheck()
            self.assertEqual(refreshed["closed_contract"]["status"], "CURRENT_PASS", refreshed)
            self.assertNotEqual(refreshed["receipt_id"], first["receipt_id"])
            self.assertIsNotNone(debt.current_tree_reverify(self.root, "T-001"))
        self.assertEqual(receipt.read_bytes(), original)

    def test_changed_environment_neither_proves_regression_nor_excuses_oracle_change(self):
        self.recheck()
        self.subject.write_text("def value(): return 99\n", encoding="utf-8")
        with patch.dict(os.environ, {"CLOSED_CONTRACT_RUNTIME_CONTROL": "changed"}):
            failed = self.recheck()
            self.assertEqual(failed["closed_contract"]["status"], "CURRENT_CHECK_FAILED", failed)
            self.oracle.write_text("import unittest\nclass Test(unittest.TestCase):\n"
                                   "    def test_nothing(self): self.assertTrue(True)\n",
                                   encoding="utf-8")
            weakened = self.recheck()
            self.assertEqual(weakened["closed_contract"]["status"], "UNVERIFIED", weakened)
            self.assertEqual(weakened["closed_contract"]["reason"], "ORACLE_CHANGED")

    def test_observer_python_does_not_replace_the_recorded_verifier(self):
        self.recheck()
        with patch.object(
            closed_contracts.execution.sys, "executable", "unrelated-observer-python"
        ):
            self.assertEqual(self.observation()["status"], "CURRENT_PASS")

    def test_dependency_hash_budget_is_explicit_and_nonblocking(self):
        self.recheck()
        with patch.object(closed_contracts, "MAX_TOTAL_BYTES", 1):
            result = closed_contracts.inspect(self.root)
        self.assertFalse(result["ok"], result)
        self.assertIn("byte limit", str(result["errors"]))
        self.assertFalse(result["blocks_unrelated_work"])

    def test_scope_only_never_claims_semantic_pass_or_failure(self):
        lineage = ensure_project_lineage(self.root)
        relative = ".saipen/kitchen/release_scope/T-001.json"
        record = {"schema_version": 2, "ticket": "T-001", "op_id": "scope-test",
                  "project_identity": project_identity(self.root), "project_lineage": lineage,
                  "paths": {
                      "subject.py": closed_contracts.execution._sha(self.subject.read_bytes())}}
        raw = json.dumps(record).encode()
        result = run_mutation(
            self.root, op_id="scope-test", operation="scope", agent="tester",
            project_identity=project_identity(self.root), semantic_payload_hash=hash_bytes(raw),
            targets=[{"path": relative, "role": "report", "action": "write", "content": raw,
                      "before_hash": "", "after_hash": hash_bytes(raw)}],
            preconditions={relative: ""}, verification_policy="none",
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.observation()["status"], "UNCHANGED_SCOPE")
        self.subject.write_text("# harmless\ndef value(): return 7\n", encoding="utf-8")
        self.assertEqual(self.observation()["status"], "REGRESSION_SUSPECT")

    def test_active_successor_is_reported_without_duplicate_work(self):
        baseline = self.recheck()
        self.assertEqual(baseline["closed_contract"]["status"], "CURRENT_PASS")
        # This legacy DONE fixture gains a real native closed source. The
        # regression observation must not reopen it or rewrite its evidence.
        captured = intake.capture(self.root, "value() must return 7", work="T-001")
        self.assertTrue(captured["ok"], captured)
        receipt = captured["receipt"]
        added = intake.add_requirement(self.root, receipt, rid="R001",
                                       text="value() returns 7")
        self.assertTrue(added["ok"], added)
        verified = intake.set_disposition(
            self.root, receipt, "R001", "VERIFIED", evidence=baseline["record"],
            verification="unittest test_contract:PASS",
        )
        self.assertTrue(verified["ok"], verified)
        closed = intake.close_receipt(self.root, receipt)
        self.assertTrue(closed["ok"], closed)
        board = self.root / ".saipen/BOARD.md"
        board.write_text(board.read_text(encoding="utf-8").replace(
            "## TODO\n", "## TODO\n- [ ] T-010 existing repair | needs: T-001\n"),
            encoding="utf-8")
        before = board.read_bytes()
        self.assertEqual(parse_board(before.decode("utf-8"))["errors"], [], before.decode("utf-8"))
        archive = self.root / ".saipen/archive/source"
        historical = {path: path.read_bytes() for path in archive.rglob("*") if path.is_file()}
        tombstone = self.root / f".saipen/intake/tombstones/{receipt}.json"
        historical[tombstone] = tombstone.read_bytes()
        self.assertTrue(historical)
        self.subject.write_text("def value(): return 99\n", encoding="utf-8")
        self.assertEqual(self.recheck()["closed_contract"]["status"], "CURRENT_REGRESSION")
        row = self.observation()
        self.assertEqual(row["active_repairs"], ["T-010"])
        self.assertIn(receipt, row["source_receipts"])
        self.assertEqual(intake.status(self.root, receipt)["status"], "CLOSED")
        self.assertEqual({path: path.read_bytes() for path in historical}, historical)
        self.assertEqual(board.read_bytes(), before)

    def test_dry_run_never_executes_focused_command_or_writes(self):
        with patch.object(debt, "_capture_findings_read_only", return_value={
            "ok": True, "exit_code": 0, "gate": "core", "problems": [], "warnings": [],
        }), patch.object(closed_contracts.execution, "_measure") as run:
            before = {path.relative_to(self.root): path.read_bytes()
                      for path in self.root.rglob("*") if path.is_file()}
            result = self.recheck(dry_run=True)
            run.assert_not_called()
            self.assertEqual(result["closed_contract"]["status"], "NOT_RUN")
            self.assertEqual(before, {path.relative_to(self.root): path.read_bytes()
                                     for path in self.root.rglob("*") if path.is_file()})

    def test_simultaneous_rechecks_keep_receipt_ids_serialized(self):
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(
                lambda agent: debt.reverify_work(
                    self.root, "T-001", agent, contract_path=self.contract
                ),
                ("tester-a", "tester-b"),
            ))
        self.assertTrue(any(result["ok"] for result in results), results)
        self.assertTrue(all(result["ok"] or result["code"] == "WRITER_BUSY"
                            for result in results), results)
        self.assertEqual(len(list((self.root / debt.REVERIFY_DIR).glob("*.json"))), 1, results)

    def test_tampered_latest_receipt_cannot_resurrect_old_pass(self):
        result = self.recheck()
        receipt = self.root / debt.REVERIFY_DIR / (result["receipt_id"] + ".json")
        body = json.loads(receipt.read_text(encoding="utf-8"))
        body["closed_contract"]["status"] = "CURRENT_REGRESSION"
        receipt.write_text(json.dumps(body), encoding="utf-8")
        result = closed_contracts.inspect(self.root)
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["blocks_unrelated_work"])

    def test_removed_binding_with_recomputed_digest_is_still_untrusted(self):
        result = self.recheck()
        receipt = self.root / debt.REVERIFY_DIR / (result["receipt_id"] + ".json")
        body = json.loads(receipt.read_text(encoding="utf-8"))
        del body["closed_contract"]
        canonical = {key: value for key, value in body.items()
                     if key not in debt._REVERIFY_UNDIGESTED}
        body["integrity_digest"] = hash_bytes(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode())
        receipt.write_text(json.dumps(body), encoding="utf-8")
        self.assertFalse(closed_contracts.inspect(self.root)["ok"])

    def test_native_read_only_cli_paginates_and_never_executes(self):
        self.recheck()
        result = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).parent / "saipen.py"),
             "--project-root", str(self.root), "--json", "work", "contracts", "T-001",
             "--limit", "0"], capture_output=True, text=True, encoding="utf-8",
            env=unbound_environment(), timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        body = json.loads(result.stdout)
        self.assertEqual(body["rows"], [])
        self.assertTrue(body["has_more"])
        self.assertTrue(body["advisory"])

    def test_invalid_input_and_legacy_binding_do_not_claim_green(self):
        self.assertEqual(self.observation()["status"], "UNVERIFIED")
        self.assertFalse(closed_contracts.inspect(self.root, "../escape")["ok"])
        self.configuration["subject_files"] = ["../escape"]
        self.contract.write_text(json.dumps(self.configuration), encoding="utf-8")
        self.assertEqual(self.recheck()["closed_contract"]["status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
