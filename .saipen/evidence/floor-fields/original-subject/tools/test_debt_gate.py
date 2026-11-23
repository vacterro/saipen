from __future__ import annotations

import contextlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import debt as debt_mod  # noqa: E402
from saipen_engine import findings as findings_mod  # noqa: E402
from saipen_engine import intake  # noqa: E402
from saipen_engine import journal as journal_mod  # noqa: E402
from saipen_engine import lock as lock_mod  # noqa: E402
from saipen_engine.lock import project_writer_lock  # noqa: E402

SCENARIO = ROOT / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"


def _canned(entries: list[tuple[str, str, str]]) -> list[dict]:
    """Build structured findings from (severity, message, category) triples."""
    return [
        findings_mod.classify(severity, message, category=category)
        for severity, message, category in entries
    ]


class FindingsIdentityTests(unittest.TestCase):
    """Phase D: stable structured identity, ordering/line stability, secrets."""

    def test_identity_is_deterministic_and_order_free(self) -> None:
        message = (
            "ticket T-102 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)"
        )
        first = findings_mod.classify("problem", message)
        second = findings_mod.classify("problem", message)
        self.assertEqual(first, second)
        other_first = findings_mod.classify(
            "problem",
            "ticket T-31 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)",
        )
        self.assertNotEqual(first["finding_key"], other_first["finding_key"])
        # same broken semantic condition, different subject: the detail
        # fingerprint is identical by design; the KEY is what separates them
        self.assertEqual(first["detail_hash"], other_first["detail_hash"])
        self.assertEqual(first["subject_id"], "T-102")
        self.assertEqual(other_first["subject_id"], "T-31")

    def test_subject_extraction_prefers_semantic_ids_over_line_numbers(self) -> None:
        one = findings_mod.classify(
            "problem",
            "mechanical provenance [saio] -- structural SAIOPS-owned events after the "
            "first provenanced event (E-4) lack `[op: ...]`, so a manual structural "
            "edit cannot be distinguished from a mechanized one: .saipen/LOG.md:410 E-605 (T-584)",
        )
        moved = findings_mod.classify(
            "problem",
            "mechanical provenance [saio] -- structural SAIOPS-owned events after the "
            "first provenanced event (E-4) lack `[op: ...]`, so a manual structural "
            "edit cannot be distinguished from a mechanized one: .saipen/LOG.md:999 E-605 (T-584)",
        )
        self.assertEqual(one["subject_id"], "E-605")
        self.assertEqual(one["finding_key"], moved["finding_key"])
        self.assertNotEqual(one.get("subject_ref"), moved.get("subject_ref"))

    def test_semantic_change_changes_detail_but_not_key_shape(self) -> None:
        before = findings_mod.classify(
            "problem",
            "ticket T-102 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)",
        )
        after = findings_mod.classify(
            "problem",
            "ticket T-102 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: unproven/failed)",
        )
        self.assertEqual(before["finding_key"], after["finding_key"])
        self.assertNotEqual(before["detail_hash"], after["detail_hash"])
        self.assertEqual(findings_mod.compare_finding(before, after), "CHANGED")
        self.assertEqual(findings_mod.compare_finding(before, dict(before)), "CARRIED")

    def test_unknown_message_is_global_and_never_carried(self) -> None:
        finding = findings_mod.classify("problem", "completely novel failure shape")
        self.assertEqual(finding["rule_id"], "unclassified")
        self.assertEqual(finding["subject_kind"], "global")
        self.assertIsNone(finding["subject_id"])

    def test_credential_finding_never_carries_message_content(self) -> None:
        secret = "sk-live-DO-NOT-LEAK-9f8e7d6c5b4a"
        message = (
            "source credential gate: SOURCE_CREDENTIALS_UNSAFE credential pattern "
            f"{secret} in exact archive source SRC-033; supply a user-authorized "
            "replacement or amendment before release"
        )
        finding = findings_mod.classify("problem", message)
        self.assertTrue(finding["credential"])
        self.assertIsNone(finding["detail"])
        self.assertEqual(finding["subject_id"], "SRC-033")
        serialized = json.dumps(finding)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("sk-live", serialized)

    def test_ruleset_fingerprint_covers_the_rule_table(self) -> None:
        fingerprint = findings_mod.ruleset_fingerprint()
        self.assertEqual(fingerprint, findings_mod.ruleset_fingerprint())
        self.assertTrue(len(findings_mod.RULE_TABLE) >= 10)


class DebtGateFixtureTests(unittest.TestCase):
    """Real-engine plumbing: snapshots, delta, fail-closed refusals."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-debt-gate-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        board = self.root / ".saipen/BOARD.md"
        text = board.read_text(encoding="utf-8")
        text = text.replace("## DOING\n- [/] T-001 DOING task", "## DOING")
        text = text.replace(
            "## DONE\n", "## DONE\n- [x] T-001 DOING task | verify: proof exists\n"
        )
        board.write_text(text, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # -- snapshot lifecycle ------------------------------------------------

    def test_snapshot_is_immutable_project_bound_and_reused(self) -> None:
        first = debt_mod.create_snapshot(self.root, "probe", "baseline capture")
        self.assertTrue(first["ok"], first)
        snapshot_id = first["snapshot_id"]
        record = debt_mod.load_snapshot(self.root, snapshot_id)
        self.assertEqual(record["snapshot_id"], snapshot_id)
        self.assertEqual(record["project_lineage"], debt_mod.project_lineage_identity(self.root))
        self.assertTrue(record["ruleset_fingerprint"])
        self.assertIn("journal_op_id", record)
        again = debt_mod.create_snapshot(self.root, "probe", "baseline capture")
        self.assertTrue(again["ok"], again)
        self.assertEqual(again["code"], "DEBT_SNAPSHOT_REUSED")
        self.assertEqual(again["snapshot_id"], snapshot_id)
        # immutability: a new checkpoint (tree changed) creates a NEW snapshot
        intake.capture(self.root, "mutation", source_kind="user_audit")
        second = debt_mod.create_snapshot(self.root, "probe", "after mutation")
        self.assertTrue(second["ok"], second)
        self.assertNotEqual(second["snapshot_id"], snapshot_id)

    def test_corrupted_snapshot_fails_closed(self) -> None:
        created = debt_mod.create_snapshot(self.root, "probe", "capture")
        self.assertTrue(created["ok"], created)
        intake.capture(
            self.root, "seed finding material", source_kind="user_audit", work="T-001"
        )
        seeded = debt_mod.create_snapshot(self.root, "probe", "non-empty capture")
        self.assertTrue(seeded["ok"], seeded)
        self.assertTrue(seeded["problem_count"] >= 1, seeded)
        path = self.root / debt_mod.DEBT_DIR / f"{seeded['snapshot_id']}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["problems"] = []
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(debt_mod.DebtRefusal) as caught:
            debt_mod.load_snapshot(self.root, seeded["snapshot_id"])
        self.assertEqual(caught.exception.code, "DEBT_SNAPSHOT_CORRUPT")

    def test_snapshot_from_another_project_refuses(self) -> None:
        # T-1516: another project is another lineage; a same-lineage copy at
        # another path keeps its baseline (test_t1516_portable_receipts).
        from saipen_engine.paths import (
            IDENTITY_NAME,
            identity_file_content,
            new_project_lineage,
        )

        created = debt_mod.create_snapshot(self.root, "probe", "capture")
        self.assertTrue(created["ok"], created)
        other = Path(self.tmp.name) / "other"
        shutil.copytree(self.root, other)
        (other / ".saipen" / IDENTITY_NAME).write_text(
            identity_file_content(new_project_lineage()), encoding="utf-8"
        )
        with self.assertRaises(debt_mod.DebtRefusal) as caught:
            debt_mod.load_snapshot(other, created["snapshot_id"])
        self.assertEqual(caught.exception.code, "DEBT_SNAPSHOT_FOREIGN_LINEAGE")

    def test_ruleset_change_refuses_comparison(self) -> None:
        created = debt_mod.create_snapshot(self.root, "probe", "capture")
        self.assertTrue(created["ok"], created)
        with patch.object(findings_mod, "RULESET_VERSION", 99), patch.object(
            findings_mod, "ruleset_fingerprint", lambda: "stale-fingerprint"
        ), self.assertRaises(debt_mod.DebtRefusal) as caught:
            debt_mod.load_snapshot(self.root, created["snapshot_id"])
        self.assertEqual(caught.exception.code, "BASELINE_RULESET_CHANGED")

    def test_deleted_snapshot_cannot_create_pass(self) -> None:
        created = debt_mod.create_snapshot(self.root, "probe", "capture")
        self.assertTrue(created["ok"], created)
        (self.root / debt_mod.DEBT_DIR / f"{created['snapshot_id']}.json").unlink()
        with self.assertRaises(debt_mod.DebtRefusal) as caught:
            debt_mod.load_snapshot(self.root, created["snapshot_id"])
        self.assertEqual(caught.exception.code, "DEBT_SNAPSHOT_MISSING")

    # -- W2-005 writer serialization + injected race -----------------------

    def test_snapshot_id_allocation_runs_inside_the_writer_boundary(self) -> None:
        """The defect was ORDER, not intent: `_next_snapshot_id` allocated
        before the writer boundary, so two concurrent snapshots could both
        read the same maximum and mint the same id."""
        events: list[str] = []

        @contextlib.contextmanager
        def spy_lock(_root):
            events.append("lock")
            try:
                yield None
            finally:
                events.append("unlock")

        real_next_id = debt_mod._next_snapshot_id

        def spy_next_id(root):
            events.append("id")
            return real_next_id(root)

        with patch.object(lock_mod, "project_writer_lock", spy_lock), patch.object(
            debt_mod, "_next_snapshot_id", side_effect=spy_next_id
        ), patch.object(
            debt_mod, "run_mutation", wraps=debt_mod.run_mutation
        ) as mutation_spy:
            result = debt_mod.create_snapshot(self.root, "probe", "boundary probe")
        self.assertTrue(result["ok"], result)
        self.assertEqual(mutation_spy.call_count, 1, "exactly one snapshot mutation")
        self.assertEqual(events, ["lock", "id", "unlock"])
        self.assertTrue(result["snapshot_id"].endswith("000001"), result)

    def test_a_second_concurrent_snapshot_refuses_instead_of_racing(self) -> None:
        """A live writer already owns the project: the snapshot apply must
        refuse WRITER_BUSY and write nothing, never slip a second writer past
        the boundary."""
        with project_writer_lock(self.root), self.assertRaises(PermissionError) as caught:
            debt_mod.create_snapshot(self.root, "probe", "concurrent probe")
        self.assertEqual(str(caught.exception), "WRITER_BUSY")
        self.assertFalse((self.root / debt_mod.DEBT_DIR).exists())

    def test_the_safe_atomic_ownership_race_is_a_conflict_not_an_escape(self) -> None:
        """`paths.safe_atomic_replace_owned` raises ValueError when the final
        node is swapped under the write. That is the same third-state event as
        a failing action: it must land on CONFLICT, not unwind out of
        `run_mutation` with the operation stranded in APPLYING."""
        real_write = journal_mod._atomic_write

        def racing_write(path, content, *, ownership_root):
            # Windows normalises the journal-relative separators to backslashes.
            if debt_mod.DEBT_DIR in str(path).replace("\\", "/"):
                raise ValueError(
                    f"generic_path {path} changed before atomic replacement"
                )
            return real_write(path, content, ownership_root=ownership_root)

        with patch.object(
            journal_mod, "_atomic_write", side_effect=racing_write
        ):
            result = debt_mod.create_snapshot(self.root, "probe", "race probe")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "CONFLICT", result)
        self.assertIn("changed before atomic replacement", result["detail"])
        self.assertFalse((self.root / debt_mod.DEBT_DIR).exists())

    # -- Work delta (real capture) ------------------------------------------

    def test_delta_resolves_and_reports_release_blocked(self) -> None:
        baseline = debt_mod.create_snapshot(self.root, "probe", "pre-work")
        self.assertTrue(baseline["ok"], baseline)
        base = debt_mod.load_snapshot(self.root, baseline["snapshot_id"])
        # the scenario base itself carries one live Core warning (root-file
        # gate / cross-doc drift); the fixture controls assertions by
        # checking the T-001 family only, never the absolute count.
        base_unresolved = [
            f for f in base["problems"]
            if f["rule_id"] == "source_receipt_unresolved_work" and f["subject_id"] == "T-001"
        ]
        self.assertEqual(len(base_unresolved), 0, base["problems"])
        # the Work's implementation introduces one real validator problem
        result = intake.capture(
            self.root, "audit body for T-001", source_kind="user_audit", work="T-001"
        )
        self.assertTrue(result["ok"], result)
        delta = debt_mod.work_delta(
            self.root,
            "T-001",
            agent="probe",
            baseline_ref=baseline["snapshot_id"],
            verification=[{"command": "unittest probe", "result": "PASS"}],
        )
        self.assertTrue(delta["ok"], delta)
        self.assertEqual(delta["code"], "WORK_DELTA_BLOCKED")
        assert any(f["subject_id"] == "T-001" for f in delta["new"]), delta["new"]
        assert delta["strict_core"]["problems"] >= 1
        self.assertFalse(delta["release_ready"])
        # the mid-work snapshot carries the problem the Work introduced
        mid_snapshot = debt_mod.create_snapshot(self.root, "probe", "mid-work")
        self.assertTrue(mid_snapshot["ok"], mid_snapshot)
        assert any(
            f["rule_id"] == "source_receipt_unresolved_work" and f["subject_id"] == "T-001"
            for f in mid_snapshot.get("problems", [])
        ), mid_snapshot
        # repaired: coverage terminal -> problem RESOLVED, delta PASSes,
        # strict Core returns to its baseline and release stays truthful
        self.assertTrue(
            intake.add_requirement(self.root, "SRC-001", rid="R001", text="the clause")["ok"]
        )
        self.assertTrue(
            intake.set_disposition(
                self.root,
                "SRC-001",
                "R001",
                "VERIFIED",
                evidence="E-1",
                verification="unittest:PASS",
            )["ok"]
        )
        resolved_delta = debt_mod.work_delta(
            self.root,
            "T-001",
            agent="probe",
            baseline_ref=mid_snapshot["snapshot_id"],
            verification=[{"command": "unittest probe", "result": "PASS"}],
        )
        self.assertTrue(resolved_delta["ok"], resolved_delta)
        self.assertEqual(resolved_delta["code"], "WORK_DELTA_PASS")
        self.assertEqual(resolved_delta["work_delta"], "PASS")
        assert any(
            f["rule_id"] == "source_receipt_unresolved_work" and f["subject_id"] == "T-001"
            for f in resolved_delta.get("resolved", [])
        ), resolved_delta
        assert resolved_delta["work_delta"] == "PASS"
        second = debt_mod.work_delta(
            self.root,
            "T-001",
            agent="probe",
            baseline_ref=mid_snapshot["snapshot_id"],
            verification=[{"command": "unittest probe", "result": "PASS"}],
        )
        self.assertEqual(second, resolved_delta)

    def test_delta_requires_verification_evidence(self) -> None:
        baseline = debt_mod.create_snapshot(self.root, "probe", "pre-work")
        self.assertTrue(baseline["ok"], baseline)
        delta = debt_mod.work_delta(
            self.root, "T-001", agent="probe", baseline_ref=baseline["snapshot_id"]
        )
        self.assertTrue(delta["ok"], delta)
        self.assertEqual(delta["code"], "WORK_DELTA_BLOCKED")
        self.assertTrue(
            any("verification" in entry["reason"] for entry in delta["blocking"]),
            delta["blocking"],
        )

    def test_delta_without_any_baseline_refuses(self) -> None:
        result = debt_mod.work_delta(
            self.root,
            "T-001",
            agent="probe",
            verification=[{"command": "probe", "result": "PASS"}],
        )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "DEBT_BASELINE_MISSING")


class WorkDeltaClassificationTests(unittest.TestCase):
    """Phase G delta classes against canned finding sets (precise control)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-debt-classify-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        board = self.root / ".saipen/BOARD.md"
        text = board.read_text(encoding="utf-8")
        text = text.replace("## DOING\n- [/] T-001 DOING task", "## DOING")
        text = text.replace(
            "## DONE\n", "## DONE\n- [x] T-001 DOING task | verify: proof exists\n"
        )
        board.write_text(text, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _delta(
        self,
        baseline_findings: list[dict],
        current_findings: list[dict],
        *,
        work: str = "T-090",
        verification: list[dict] | None = None,
    ) -> dict:
        with patch.object(
            debt_mod,
            "capture_findings",
            return_value={
                "ok": True,
                "exit_code": 1,
                "gate": "core",
                "problems": baseline_findings,
                "warnings": [],
            },
        ):
            baseline = debt_mod.create_snapshot(self.root, "probe", "baseline")
            self.assertTrue(baseline["ok"], baseline)
        with patch.object(
            debt_mod,
            "capture_findings",
            return_value={
                "ok": True,
                "exit_code": 1,
                "gate": "core",
                "problems": current_findings,
                "warnings": [],
            },
        ):
            return debt_mod.work_delta(
                self.root,
                work,
                agent="probe",
                baseline_ref=baseline["snapshot_id"],
                verification=verification
                or [{"command": "probe tests", "result": "PASS"}],
            )

    def _finding(self, message: str, severity: str = "problem") -> dict:
        return findings_mod.classify(severity, message)

    def test_carried_unrelated_problem_passes_but_keeps_release_blocked(self) -> None:
        message = (
            "ticket T-050 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)"
        )
        baseline = [self._finding(message)]
        report = self._delta(baseline, [self._finding(message)])
        self.assertEqual(report["code"], "WORK_DELTA_PASS")
        self.assertEqual(report["carried_problems"], 1)
        self.assertEqual(report["carried"][0]["subject_id"], "T-050")
        self.assertFalse(report["release_ready"])
        self.assertFalse(report["strict_core"]["ok"])

    def test_new_problem_blocks(self) -> None:
        carried = (
            "ticket T-050 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)"
        )
        fresh = (
            "ticket T-051 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)"
        )
        report = self._delta(
            [self._finding(carried)], [self._finding(carried), self._finding(fresh)]
        )
        self.assertEqual(report["code"], "WORK_DELTA_BLOCKED")
        self.assertEqual(len(report["new"]), 1)
        self.assertEqual(report["new"][0]["subject_id"], "T-051")

    def test_worsened_problem_blocks(self) -> None:
        warning = findings_mod.classify(
            "warning",
            "ticket T-060 has no ticket-bearing closure event; legacy evidence is not "
            "recorded and is not fabricated",
            category="legacy-closure-evidence",
        )
        problem = findings_mod.classify(
            "problem",
            "ticket T-060 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: unproven/failed)",
        )
        # same rule+subject identity escalated from warning to problem
        problem["finding_key"] = warning["finding_key"]
        report = self._delta([problem], [problem])
        self.assertEqual(report["code"], "WORK_DELTA_PASS")  # same problem set as baseline
        escalated = self._delta([], [problem])
        self.assertEqual(escalated["code"], "WORK_DELTA_BLOCKED")
        self.assertEqual(len(escalated["new"]), 1)

    def test_changed_unsafe_problem_blocks(self) -> None:
        before = findings_mod.classify(
            "problem",
            "ticket T-070 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)",
        )
        after = findings_mod.classify(
            "problem",
            "ticket T-070 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: unproven/failed)",
        )
        report = self._delta([before], [after])
        self.assertEqual(report["code"], "WORK_DELTA_BLOCKED")
        self.assertEqual(len(report["changed_unsafe"]), 1)

    def test_resolved_problem_is_reported(self) -> None:
        message = (
            "ticket T-080 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)"
        )
        report = self._delta([self._finding(message)], [])
        self.assertEqual(report["code"], "WORK_DELTA_PASS")
        self.assertEqual(len(report["resolved"]), 1)
        self.assertEqual(report["resolved"][0]["subject_id"], "T-080")

    def test_work_attribution_blocks(self) -> None:
        message = (
            "ticket T-090 is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)"
        )
        baseline = [self._finding(message)]
        report = self._delta(baseline, [self._finding(message)], work="T-090")
        self.assertEqual(report["code"], "WORK_DELTA_BLOCKED")
        self.assertTrue(
            any("attributed to Work T-090" in entry["reason"] for entry in report["blocking"]),
            report["blocking"],
        )

    def test_unattributed_global_problem_blocks_even_when_carried(self) -> None:
        message = "completely novel global failure shape"
        baseline = [self._finding(message)]
        report = self._delta(baseline, [self._finding(message)])
        self.assertEqual(report["code"], "WORK_DELTA_BLOCKED")
        self.assertTrue(
            any("unattributed" in entry["reason"] for entry in report["blocking"]),
            report["blocking"],
        )


class LegacyBootstrapTests(unittest.TestCase):
    """Phase J: provenance-aware retroactive adjudication, fail-closed."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-debt-legacy-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        log_path = self.root / ".saipen/LOG.md"
        # Claim boundary E-816; pre-claim work T-050; post-claim work T-200.
        lines = [
            "- 05.09.26 00:19 [E-815] [parent: E-814] [T-050] [agent: probe] [op: op-a] "
            "DEC: pre-claim work created",
            "- 05.09.26 00:20 [E-816] [parent: E-815] [T-158] [agent: probe] [op: op-b] "
            "DEC: claimed via SAIOPS -- owner probe",
            "- 05.09.26 00:21 [E-817] [parent: E-816] [T-200] [agent: probe] [op: op-c] "
            "DEC: post-claim work created",
        ]
        log_path.write_text(
            log_path.read_text(encoding="utf-8") + "\n".join(lines) + "\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _legacy(self, findings_list: list[dict], *, target_source: str | None = None) -> dict:
        with patch.object(
            debt_mod,
            "capture_findings",
            return_value={
                "ok": True,
                "exit_code": 1,
                "gate": "core",
                "problems": findings_list,
                "warnings": [],
            },
        ):
            return debt_mod.work_delta(
                self.root,
                "T-158",
                agent="probe",
                claim_boundary="E-816",
                target_source=target_source,
                verification=[{"command": "regression_t158.py", "result": "PASS"}],
            )

    def _closure_finding(self, ticket: str) -> dict:
        return findings_mod.classify(
            "problem",
            f"ticket {ticket} is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)",
        )

    def test_pre_claim_unrelated_subject_is_carried(self) -> None:
        report = self._legacy([self._closure_finding("T-050")])
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["mode"], "legacy")
        self.assertEqual(report["carried_problems"], 1)
        self.assertEqual(report["code"], "WORK_DELTA_PASS")

    def test_target_work_subject_refuses(self) -> None:
        report = self._legacy([self._closure_finding("T-158")])
        self.assertEqual(report["code"], "WORK_DELTA_BLOCKED")
        self.assertTrue(
            any("subject is the target Work" in entry["reason"] for entry in report["blocking"]),
            report["blocking"],
        )

    def test_post_claim_subject_refuses(self) -> None:
        report = self._legacy([self._closure_finding("T-200")])
        self.assertEqual(report["code"], "WORK_DELTA_BLOCKED")
        self.assertTrue(
            any("after claim boundary" in entry["reason"] for entry in report["blocking"]),
            report["blocking"],
        )

    def test_target_source_receipt_refuses(self) -> None:
        finding = findings_mod.classify(
            "problem",
            "active receipt SRC-036 contract/coverage invalid: broken",
        )
        report = self._legacy([finding], target_source="SRC-036")
        self.assertEqual(report["code"], "WORK_DELTA_BLOCKED")
        self.assertTrue(
            any(
                "target Work's source receipt" in entry["reason"]
                for entry in report["blocking"]
            ),
            report["blocking"],
        )

    def test_global_problem_refuses(self) -> None:
        finding = findings_mod.classify("problem", "completely novel global failure")
        report = self._legacy([finding])
        self.assertEqual(report["code"], "WORK_DELTA_BLOCKED")
        self.assertTrue(
            any("unattributed" in entry["reason"] for entry in report["blocking"]),
            report["blocking"],
        )

    def test_claim_boundary_must_exist(self) -> None:
        with patch.object(
            debt_mod,
            "capture_findings",
            return_value={
                "ok": True, "exit_code": 1, "gate": "core", "problems": [], "warnings": [],
            },
        ):
            result = debt_mod.work_delta(
                self.root,
                "T-158",
                agent="probe",
                claim_boundary="E-999999",
                verification=[{"command": "probe", "result": "PASS"}],
            )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "VALIDATION_FAILED")


class _CountingProblems(list):
    """A `problems` list that counts how many times it is fully iterated.

    Each iteration of `current_problems` inside `work_delta` is one full pass
    over the current finding set, so the counter pins how many times the
    per-baseline-key comprehension over that set can have been rebuilt.
    """

    def __init__(self, items: list[dict]) -> None:
        super().__init__(items)
        self.passes = 0

    def __iter__(self):
        self.passes += 1
        return super().__iter__()


class Perf003SinglePassTests(unittest.TestCase):
    """T-1537 PERF-003: the debt gate derives each of these exactly ONCE.

    Both counters, never a clock: the assertions are about how many times the
    work happened, so they are deterministic on any machine. The computed
    report is unchanged by the hoists -- only the read count is.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-debt-perf003-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        log_path = self.root / ".saipen/LOG.md"
        lines = [
            "- 05.09.26 00:19 [E-815] [parent: E-814] [T-050] [agent: probe] [op: op-a] "
            "DEC: pre-claim work created",
            "- 05.09.26 00:20 [E-816] [parent: E-815] [T-158] [agent: probe] [op: op-b] "
            "DEC: claimed via SAIOPS -- owner probe",
            "- 05.09.26 00:21 [E-817] [parent: E-816] [T-200] [agent: probe] [op: op-c] "
            "DEC: post-claim work created",
        ]
        log_path.write_text(
            log_path.read_text(encoding="utf-8") + "\n".join(lines) + "\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _closure_finding(self, ticket: str) -> dict:
        return findings_mod.classify(
            "problem",
            f"ticket {ticket} is ## DONE but carries no current-cycle verification "
            "evidence (classifier: no current-cycle VERIFY boundary)",
        )

    def _capture(self, problems: list[dict]) -> dict:
        return {
            "ok": True,
            "exit_code": 1,
            "gate": "core",
            "problems": problems,
            "warnings": [],
        }

    def test_current_problem_keys_is_built_once_per_work_delta(self) -> None:
        """`current_problem_keys` is built ONCE per call, not once per
        baseline key (PERF-003 nested set rebuild)."""
        passes_at_size: list[int] = []
        for size in (1, 5):
            tickets = tuple(f"T-{60 + n}" for n in range(size))
            baseline = [self._closure_finding(t) for t in tickets]
            with patch.object(
                debt_mod, "capture_findings", return_value=self._capture(baseline)
            ):
                snapshot = debt_mod.create_snapshot(self.root, "probe", "baseline")
            self.assertTrue(snapshot["ok"], snapshot)
            # Only the FIRST baseline finding survives: size-1 are resolved,
            # so the resolved pass really does walk every baseline key.
            current = _CountingProblems([self._closure_finding(tickets[0])])
            with patch.object(
                debt_mod, "capture_findings", return_value=self._capture(current)
            ):
                report = debt_mod.work_delta(
                    self.root,
                    "T-090",
                    agent="probe",
                    baseline_ref=snapshot["snapshot_id"],
                    verification=[{"command": "probe tests", "result": "PASS"}],
                )
            self.assertTrue(report["ok"], report)
            self.assertEqual(len(report["resolved"]), size - 1)
            passes_at_size.append(current.passes)
        # A per-baseline-key rebuild scales with the baseline; a single hoist
        # does not. Same count at both sizes == built once, not once per key.
        self.assertEqual(
            passes_at_size[0],
            passes_at_size[1],
            f"current-key set rebuild scales with baseline size: {passes_at_size}",
        )

    def test_work_delta_reads_canonical_history_once(self) -> None:
        """`read_history_snapshot` is called exactly ONCE per `work_delta`
        call, whatever the number of Work findings (PERF-003)."""
        from saipen_engine import log as log_mod

        calls: list[int] = []
        original = log_mod.read_history_snapshot

        def counting(project_root, **kwargs):
            calls.append(1)
            return original(project_root, **kwargs)

        # Four Work findings across every adjudication branch: pre-claim
        # (carried), post-claim (blocking), and never-seen (no history).
        problems = [
            self._closure_finding(t) for t in ("T-050", "T-200", "T-201", "T-202")
        ]
        with patch.object(
            log_mod, "read_history_snapshot", counting
        ), patch.object(
            debt_mod, "capture_findings", return_value=self._capture(problems)
        ):
            report = debt_mod.work_delta(
                self.root,
                "T-158",
                agent="probe",
                claim_boundary="E-816",
                verification=[{"command": "regression_t158.py", "result": "PASS"}],
            )
        self.assertEqual(len(calls), 1, "canonical history must be read once per call")
        self.assertEqual(report["mode"], "legacy")
        self.assertEqual(report["carried_problems"], 1)

    def test_history_read_is_invocation_local_not_cached(self) -> None:
        """The single read is not a memo: a second call in the same process
        re-reads, so `current_tree_reverify` semantics stay intact."""
        from saipen_engine import log as log_mod

        calls: list[int] = []
        original = log_mod.read_history_snapshot

        def counting(project_root, **kwargs):
            calls.append(1)
            return original(project_root, **kwargs)

        problems = [self._closure_finding("T-050")]
        for _ in range(2):
            with patch.object(
                log_mod, "read_history_snapshot", counting
            ), patch.object(
                debt_mod, "capture_findings", return_value=self._capture(problems)
            ):
                report = debt_mod.work_delta(
                    self.root,
                    "T-158",
                    agent="probe",
                    claim_boundary="E-816",
                    verification=[{"command": "regression_t158.py", "result": "PASS"}],
                )
            self.assertTrue(report["ok"], report)
        self.assertEqual(len(calls), 2, "no cross-mutation cache: 1 read per call, 2 calls")


class StrictGateInvariantTests(unittest.TestCase):
    """Phase E/H: strict validation semantics are untouched by the feature."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-debt-strict-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        board = self.root / ".saipen/BOARD.md"
        text = board.read_text(encoding="utf-8")
        text = text.replace("## DOING\n- [/] T-001 DOING task", "## DOING")
        text = text.replace(
            "## DONE\n", "## DONE\n- [x] T-001 DOING task | verify: proof exists\n"
        )
        board.write_text(text, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_strict_core_stays_red_with_carried_debt(self) -> None:
        intake.capture(self.root, "audit body", source_kind="user_audit", work="T-001")
        capture = debt_mod.capture_findings(self.root)
        self.assertTrue(capture["ok"], capture)
        self.assertNotEqual(capture["exit_code"], 0)
        unresolved = [
            f for f in capture["problems"]
            if f["rule_id"] == "source_receipt_unresolved_work" and f["subject_id"] == "T-001"
        ]
        self.assertEqual(len(unresolved), 1, capture["problems"])

    def test_debt_feature_adds_no_ignore_path(self) -> None:
        source = (ROOT / "tools" / "saipen_engine" / "debt.py").read_text(encoding="utf-8")
        self.assertNotIn("--ignore-errors", source)
        self.assertNotIn("--force-pass", source)
        validate_source = (ROOT / "tools" / "validate.py").read_text(encoding="utf-8")
        self.assertNotIn("--ignore-errors", validate_source)
        self.assertNotIn("--force-pass", validate_source)

    def test_findings_json_side_artifact_matches_standard_counts(self) -> None:
        import subprocess

        intake.capture(self.root, "audit body", source_kind="user_audit", work="T-001")
        out = self.root.parent / "findings.json"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "validate.py"),
                "--project-root",
                str(self.root),
                "--findings-json",
                str(out),
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        doc = json.loads(out.read_text(encoding="utf-8"))
        unresolved = [
            f for f in doc["problems"]
            if f["rule_id"] == "source_receipt_unresolved_work" and f["subject_id"] == "T-001"
        ]
        self.assertEqual(len(unresolved), 1, doc["problems"])
        self.assertIn(unresolved[0]["finding_key"], [f["finding_key"] for f in doc["problems"]])


if __name__ == "__main__":
    unittest.main()
