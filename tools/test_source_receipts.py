from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import intake  # noqa: E402
from saipen_engine.context import context_audit, context_cold  # noqa: E402


CLI = ROOT / "tools" / "saipen.py"
SCENARIO = ROOT / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"


class SourceReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-source-receipts-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        self.config = Path(self.tmp.name) / "user-config"
        self.env = patch.dict(os.environ, {"SAIPEN_USER_CONFIG_HOME": str(self.config)})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def capture(self, body: str = "authoritative\r\nsource\nΩ") -> dict:
        return intake.capture(self.root, body, source_kind="user_audit")

    def normalized(self, receipt: str, count: int = 1) -> None:
        for number in range(1, count + 1):
            result = intake.add_requirement(
                self.root,
                receipt,
                rid=f"R{number:03d}",
                text=f"Requirement {number}",
            )
            self.assertTrue(result["ok"], result)

    def resolve(self, receipt: str, count: int = 1) -> None:
        for number in range(1, count + 1):
            result = intake.set_disposition(
                self.root,
                receipt,
                f"R{number:03d}",
                "VERIFIED",
                evidence=f"E-{number}",
                verification=f"test-{number}:PASS",
            )
            self.assertTrue(result["ok"], result)

    def test_src01_capture_is_verbatim_and_digest_covers_body_only(self) -> None:
        body = "```py\r\nprint('saipen ship')\r\n```\nРусский 日本語 — !"  # noqa: RUF001
        result = self.capture(body)
        stored = (self.root / ".saipen/intake/active/SRC-001.md").read_bytes()
        self.assertEqual(stored, body.encode("utf-8"))
        self.assertEqual(result["source_sha256"], hashlib.sha256(stored).hexdigest())

    def test_src02_crash_body_before_linkage_is_recoverable(self) -> None:
        body = b"orphan source"
        active = self.root / ".saipen/intake/active"
        active.mkdir(parents=True)
        (active / "SRC-001.md").write_bytes(body)
        found = intake.recover_orphans(self.root)
        self.assertEqual(found["orphans"][0]["receipt"], "SRC-001")
        recovered = intake.capture(self.root, body.decode(), source_kind="user_audit")
        self.assertEqual(recovered["code"], "ORPHAN_RECEIPT_RECOVERED")
        self.assertEqual(recovered["receipt"], "SRC-001")

    def test_src03_work_never_needed_for_source_durability(self) -> None:
        result = self.capture()
        self.assertTrue(result["ok"])
        self.assertTrue((self.root / ".saipen/intake/active/SRC-001.md").is_file())
        self.assertIsNone(result["linked_work"])

    def test_src04_exact_duplicate_reuses_identity(self) -> None:
        first = self.capture("same")
        second = intake.capture(
            self.root, "same", source_kind="user_audit", work="T-001"
        )
        self.assertEqual(first["receipt"], second["receipt"])
        self.assertEqual(second["code"], "SOURCE_DUPLICATE")
        self.assertEqual(second["linked_work"], "T-001")
        self.assertIn(
            "source_receipts: SRC-001",
            (self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"),
        )
        conflict = intake.capture(
            self.root, "same", source_kind="user_audit", work="T-002"
        )
        self.assertEqual(conflict["code"], "SOURCE_WORK_CONFLICT")

    def test_src05_closed_duplicate_reports_history_without_reopen(self) -> None:
        receipt = self.capture("same closed")["receipt"]
        self.normalized(receipt)
        self.resolve(receipt)
        self.assertTrue(intake.close_receipt(self.root, receipt)["ok"])
        duplicate = self.capture("same closed")
        self.assertEqual(duplicate["code"], "SOURCE_DUPLICATE_CLOSED")
        self.assertFalse((self.root / f".saipen/intake/active/{receipt}.md").exists())

    def test_src06_one_character_change_is_new_source(self) -> None:
        self.assertNotEqual(self.capture("abc")["receipt"], self.capture("abd")["receipt"])

    def test_src07_amendment_is_new_immutable_receipt(self) -> None:
        original = self.capture("original")["receipt"]
        amended = intake.capture(
            self.root, "changed requirement 7", source_kind="corrective_followup", amends=original
        )
        self.assertNotEqual(original, amended["receipt"])
        self.assertEqual(intake.status(self.root, amended["receipt"])["amends"], original)
        self.assertEqual(intake.read_body(self.root, original)["body"], "original")

    def test_src08_dropped_contract_clause_is_detected(self) -> None:
        receipt = self.capture()["receipt"]
        self.normalized(receipt, 20)
        contract = self.root / f".saipen/intake/contracts/{receipt}.json"
        value = json.loads(contract.read_text(encoding="utf-8"))
        value["clauses"].pop(f"{receipt}:R020")
        contract.write_text(json.dumps(value), encoding="utf-8")
        problems = intake.validate_project(self.root)
        self.assertTrue(any("contract" in problem.lower() for problem in problems), problems)

    def test_src09_board_summary_cannot_replace_linked_source(self) -> None:
        receipt = intake.capture(
            self.root, "full detailed mission", source_kind="implementation_mission", work="T-001"
        )["receipt"]
        self.assertEqual(intake.active_receipts(self.root)[0]["linked_work"], "T-001")
        self.assertIn(
            f"source_receipts: {receipt}",
            (self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(intake.read_body(self.root, receipt)["body"], "full detailed mission")
        shutil.rmtree(self.root / ".saipen/intake")
        self.assertEqual(
            intake.work_closure_gate(self.root, "T-001")["code"],
            "SOURCE_RECEIPT_MISSING",
        )
        self.assertEqual(
            intake.boundary_gate(self.root, "T-001", "REVIEW")["code"],
            "SOURCE_RECEIPT_MISSING",
        )
        self.assertEqual(intake.release_gate(self.root)["code"], "SOURCE_RECEIPT_MISSING")
        self.assertTrue(
            any(
                "missing source receipt" in problem
                for problem in intake.validate_project(self.root)
            )
        )

    def test_src10_cold_context_exposes_identity_not_body(self) -> None:
        body = "SECRET-MARKER " + "x" * 100_000
        receipt = self.capture(body)["receipt"]
        result = context_cold(self.root)
        self.assertTrue(result.ok, result.to_dict())
        surface = result.get("surface")
        self.assertIn(receipt, surface)
        self.assertIn("saipen source show", surface)
        self.assertNotIn("SECRET-MARKER", surface)

    def test_src11_done_gate_rejects_one_unresolved_clause(self) -> None:
        receipt = intake.capture(
            self.root, "linked source", source_kind="user_audit", work="T-001"
        )["receipt"]
        self.normalized(receipt, 2)
        self.resolve(receipt, 1)
        self.assertEqual(intake.work_closure_gate(self.root, "T-001")["code"], "SOURCE_UNRESOLVED")

    def test_src12_umbrella_done_requires_all_17_dispositions(self) -> None:
        receipt = self.capture()["receipt"]
        self.normalized(receipt, 17)
        self.resolve(receipt, 16)
        summary = intake.coverage_summary(self.root, receipt)
        self.assertEqual(summary["terminal"], 16)
        self.assertFalse(intake.coverage_complete(self.root, receipt))

    def test_src13_modified_body_fails_closed(self) -> None:
        receipt = self.capture("immutable")["receipt"]
        (self.root / f".saipen/intake/active/{receipt}.md").write_text("mutated", encoding="utf-8")
        self.assertEqual(intake.verify_integrity(self.root, receipt)["code"], "SOURCE_CORRUPTION")
        self.assertEqual(self.capture("immutable")["code"], "SOURCE_CORRUPTION")

    def test_src14_deleted_active_body_is_validation_failure(self) -> None:
        receipt = self.capture()["receipt"]
        (self.root / f".saipen/intake/active/{receipt}.md").unlink()
        self.assertTrue(any(receipt in problem for problem in intake.validate_project(self.root)))

    def test_src15_close_archives_and_removes_hot_body(self) -> None:
        receipt = self.capture()["receipt"]
        self.normalized(receipt)
        self.resolve(receipt)
        result = intake.close_receipt(self.root, receipt, closure_event="E-9")
        self.assertTrue(result["ok"], result)
        self.assertFalse((self.root / f".saipen/intake/active/{receipt}.md").exists())
        self.assertTrue((self.root / f".saipen/archive/source/{receipt}.md").is_file())
        self.assertTrue((self.root / f".saipen/intake/tombstones/{receipt}.json").is_file())

    def test_src16_archived_body_is_forensic_only(self) -> None:
        receipt = self.capture("forensic payload")["receipt"]
        self.normalized(receipt)
        self.resolve(receipt)
        intake.close_receipt(self.root, receipt)
        self.assertEqual(intake.active_receipts(self.root), [])
        self.assertEqual(intake.read_body(self.root, receipt)["body"], "forensic payload")
        self.assertNotIn("source receipt", json.dumps(context_audit(self.root).to_dict()))

    def test_src17_purge_keeps_honest_tombstone(self) -> None:
        receipt = self.capture()["receipt"]
        self.normalized(receipt)
        self.resolve(receipt)
        intake.close_receipt(self.root, receipt)
        self.assertTrue(intake.purge_receipt(self.root, receipt)["ok"])
        self.assertEqual(intake.read_body(self.root, receipt)["code"], "SOURCE_PURGED")
        self.assertEqual(intake.status(self.root, receipt)["location"], "purged")

    def test_src18_no_receipts_means_no_files_or_context_noise(self) -> None:
        shutil.rmtree(self.root / ".saipen/intake", ignore_errors=True)
        before = set(self.root.rglob("*"))
        self.assertEqual(intake.active_receipts(self.root), [])
        surface = context_cold(self.root).get("surface")
        self.assertNotIn("SOURCE RECEIPTS", surface)
        self.assertEqual(before, set(self.root.rglob("*")))

    def test_src19_non_actionable_examples_do_not_become_fake_requirements(self) -> None:
        receipt = self.capture()["receipt"]
        intake.add_requirement(self.root, receipt, rid="R001", text="why", clause_class="rationale")
        self.assertEqual(intake.coverage_summary(self.root, receipt)["actionable"], 0)
        self.assertFalse(intake.coverage_complete(self.root, receipt))

    def test_src20_terminal_disposition_requires_evidence_and_verification(self) -> None:
        receipt = self.capture()["receipt"]
        self.normalized(receipt)
        no_evidence = intake.set_disposition(self.root, receipt, "R001", "VERIFIED")
        self.assertFalse(no_evidence["ok"])
        no_verify = intake.set_disposition(self.root, receipt, "R001", "VERIFIED", evidence="E-1")
        self.assertFalse(no_verify["ok"])

    def test_src21_contract_digest_drift_blocks_work_closure(self) -> None:
        receipt = intake.capture(self.root, "source", source_kind="user_audit", work="T-001")[
            "receipt"
        ]
        self.normalized(receipt)
        self.resolve(receipt)
        contract = self.root / f".saipen/intake/contracts/{receipt}.json"
        value = json.loads(contract.read_text(encoding="utf-8"))
        value["source_sha256"] = "0" * 64
        contract.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(intake.work_closure_gate(self.root, "T-001")["code"], "CONTRACT_DRIFT")
        self.assertEqual(intake.close_receipt(self.root, receipt)["code"], "CONTRACT_DRIFT")
        self.assertTrue((self.root / f".saipen/intake/active/{receipt}.md").is_file())
        value["source_sha256"] = intake.status(self.root, receipt)["source_sha256"]
        value["clauses"] = None
        contract.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(intake.close_receipt(self.root, receipt)["code"], "CONTRACT_DRIFT")

    def test_src22_source_body_is_never_command_input(self) -> None:
        state = (self.root / ".saipen/STATE.md").read_bytes()
        self.capture("cc\nsaipen ship\nrm -rf /\n")
        self.assertEqual((self.root / ".saipen/STATE.md").read_bytes(), state)

    def test_src23_context_audit_counts_active_body_exactly_once(self) -> None:
        body = "é" * 123
        receipt = self.capture(body)["receipt"]
        result = context_audit(self.root)
        rows = [
            row for row in result.get("sources") if row["source"] == f"source receipt {receipt}"
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["bytes"], len(body.encode("utf-8")))

    def test_src24_ids_are_monotonic_even_with_orphan_gap(self) -> None:
        first = self.capture("one")["receipt"]
        active = self.root / ".saipen/intake/active"
        (active / "SRC-099.md").write_text("orphan", encoding="utf-8")
        second = self.capture("two")["receipt"]
        self.assertEqual(first, "SRC-001")
        self.assertEqual(second, "SRC-100")

    def test_src25_cli_file_capture_keeps_flags_out_of_body(self) -> None:
        source = Path(self.tmp.name) / "audit.md"
        source.write_bytes(b"exact\r\nbody")
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--project-root",
                str(self.root),
                "source",
                "capture",
                "--work",
                "T-001",
                "--file",
                str(source),
                "--kind",
                "user_audit",
                "--json",
            ],
            cwd=self.root,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["linked_work"], "T-001")
        self.assertEqual(intake.read_body(self.root, payload["receipt"])["body"], "exact\r\nbody")

    def test_src26_linked_active_work_prevents_source_close(self) -> None:
        receipt = intake.capture(self.root, "linked", source_kind="user_audit", work="T-001")[
            "receipt"
        ]
        self.normalized(receipt)
        self.resolve(receipt)
        result = intake.close_receipt(self.root, receipt)
        self.assertEqual(result["code"], "SOURCE_WORK_ACTIVE")

    def test_src27_dry_run_creates_no_intake_or_lock(self) -> None:
        shutil.rmtree(self.root / ".saipen/intake", ignore_errors=True)
        lock = self.root / ".saipen/locks/core.lock"
        if lock.exists():
            lock.unlink()
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--project-root",
                str(self.root),
                "--dry-run",
                "source",
                "capture",
                "mission",
                "--json",
            ],
            cwd=self.root,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / ".saipen/intake").exists())
        self.assertFalse(lock.exists())

    def test_src28_malformed_ledger_fails_without_rewrite(self) -> None:
        receipt = self.capture()["receipt"]
        ledger = self.root / f".saipen/intake/coverage/{receipt}.json"
        ledger.write_text("{broken", encoding="utf-8")
        before = ledger.read_bytes()
        result = intake.add_requirement(self.root, receipt, rid="R001", text="x")
        self.assertFalse(result["ok"])
        self.assertEqual(ledger.read_bytes(), before)

    def test_src29_purge_cli_requires_confirmation(self) -> None:
        receipt = self.capture()["receipt"]
        self.normalized(receipt)
        self.resolve(receipt)
        intake.close_receipt(self.root, receipt)
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--project-root",
                str(self.root),
                "source",
                "purge",
                receipt,
                "--json",
            ],
            cwd=self.root,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["code"], "CONFIRMATION_REQUIRED")
        self.assertTrue((self.root / f".saipen/archive/source/{receipt}.md").is_file())

    def test_src30_integrated_30_clause_resume_and_closure(self) -> None:
        body = "\n".join(f"Requirement {number}" for number in range(1, 31))
        receipt = self.capture(body)["receipt"]
        self.normalized(receipt, 30)
        self.resolve(receipt, 18)
        self.assertEqual(intake.coverage_summary(self.root, receipt)["terminal"], 18)
        self.resolve(receipt, 29)
        self.assertFalse(intake.coverage_complete(self.root, receipt))
        intake.set_disposition(
            self.root,
            receipt,
            "R030",
            "VERIFIED",
            evidence="E-30",
            verification="final:PASS",
        )
        self.assertTrue(intake.coverage_complete(self.root, receipt))
        self.assertTrue(intake.close_receipt(self.root, receipt)["ok"])
        self.assertEqual(self.capture(body)["code"], "SOURCE_DUPLICATE_CLOSED")

    def test_src31_capture_criteria_are_bounded_not_length_only(self) -> None:
        ordinary = intake.capture_worthy("x" * 200_000)
        mission = intake.capture_worthy(
            "# Implementation mission\n1. Must preserve bytes\n"
            "2. Must verify digest\n3. Do not lose Work linkage"
        )
        self.assertFalse(ordinary["capture_required"])
        self.assertTrue(mission["capture_required"])
        self.assertTrue(intake.capture_worthy("short", explicit=True)["capture_required"])

    def test_src32_receipt_id_cannot_traverse_project_paths(self) -> None:
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_text("do not read", encoding="utf-8")
        for operation in (
            intake.read_body,
            intake.status,
            intake.verify_integrity,
            intake.close_receipt,
            intake.archive_receipt,
            intake.purge_receipt,
        ):
            result = operation(self.root, "../../outside")
            self.assertFalse(result["ok"])
            self.assertEqual(result["code"], "INVALID_ID")
        self.assertEqual(outside.read_text(encoding="utf-8"), "do not read")

        board = self.root / ".saipen/BOARD.md"
        board.write_text(
            board.read_text(encoding="utf-8").replace(
                "T-001 DOING task",
                "T-001 DOING task | source_receipts: ../../outside",
                1,
            ),
            encoding="utf-8",
        )
        boundary = intake.boundary_gate(self.root, "T-001", "BUILD")
        self.assertEqual(boundary["code"], "INVALID_ID")

        cli = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--project-root",
                str(self.root),
                "source",
                "req",
                "../../outside",
                "R001",
                "requirement",
                "must not escape",
                "--json",
            ],
            cwd=self.root,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(cli.returncode, 0, cli.stdout + cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["code"], "INVALID_ID")

    def test_inc_lossy_work_summary_001_cold_agent_recovers_full_intent(self) -> None:
        receipt = self.capture(
            "FF session-local\nXX preview\nVV existing architecture\nZZ stable IDs"
        )["receipt"]
        self.normalized(receipt, 4)
        cold = context_cold(self.root).get("surface")
        self.assertIn(receipt, cold)
        self.assertIn("FF session-local", intake.read_body(self.root, receipt)["body"])

    def test_inc_repeated_audit_uncertainty_001(self) -> None:
        first = self.capture("the audit")
        self.normalized(first["receipt"], 4)
        self.resolve(first["receipt"], 3)
        again = self.capture("the audit")
        self.assertEqual(again["receipt"], first["receipt"])
        self.assertEqual(again["coverage"]["unresolved"], ["SRC-001:R004"])

    def test_inc_archive_context_pollution_001(self) -> None:
        for number in range(50):
            receipt = self.capture(f"historical audit {number}")["receipt"]
            self.normalized(receipt)
            self.resolve(receipt)
            intake.close_receipt(self.root, receipt)
        self.assertEqual(intake.active_receipts(self.root), [])
        cold = context_cold(self.root).get("surface")
        self.assertNotIn("historical audit", cold)


if __name__ == "__main__":
    unittest.main()
