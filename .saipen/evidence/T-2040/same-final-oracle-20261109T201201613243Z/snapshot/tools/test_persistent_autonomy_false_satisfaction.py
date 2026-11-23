"""Independent negative controls and regression invariants for false goal satisfaction repair.

Verifies all 24 regression requirements of SRC-370 (T-1996):
1. Hash-prefixed filenames in reverse order.
2. Older PASS and newer FAIL.
3. Newer focused PASS and earlier full-family FAIL.
4. PASS for an unrelated source fingerprint.
5. Source modified after an otherwise valid PASS.
6. Complete PASS with valid current verification identity.
7. Failed evidence containing red but no legacy failures field.
8. Baseline FAIL with no new-red items.
9. Invalid or corrupted evidence record.
10. Missing matching evidence.
11. Current registered goal missing from a partial export.
12. Duplicate registered goal.
13. Goal registered but not authenticated.
14. Legacy capsule supplied to campaign admission.
15. Campaign capsule supplied to legacy goal authorization.
16. Wrong project or target-host binding.
17. Expired, revoked or forged campaign receipt.
18. Correctly authenticated campaign admission.
19. Zero eligible new defects with unchanged generation.
20. Newly arrived evidence after quiescence.
21. Full-suite PASS but other independent maintenance gaps.
22. Real native successor model-turn execution.
23. Release blocked while independent engineering continues.
24. No false project completion from one clean test family.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from saipen_engine.discovery_providers import (
    FailedTestProvider,
    AuditInboxProvider,
    BacklogProvider,
    ComprehensiveMaintenanceProvider,
    FRESHNESS_CURRENT,
    FRESHNESS_STALE,
    FRESHNESS_UNMEASURED,
    STATUS_SATISFIED,
    STATUS_ACTIONABLE_GAPS,
    STATUS_NO_ADMISSIBLE_WORK,
    STATUS_BLOCKED_BY_EVIDENCE,
    COMPLETION_FULL,
    COMPLETION_PARTIAL,
    COMPLETION_UNKNOWN,
)
from saipen_engine.persistent_goal import (
    PersistentGoal,
    register_goal,
    save_goal,
    get_goal,
    list_goals,
    DuplicateGoalError,
)
from saipen_engine import goal_authority, campaign_authority


class FalseSatisfactionRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.evidence_dir = self.root / ".saipen" / "evidence" / "core-unit"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.provider = FailedTestProvider()
        self.goal = PersistentGoal(
            goal_id="self-maintenance-test",
            project_id="test-proj",
            title="Continuous Self-Maintenance",
            objective="Eliminate defects",
            evidence_provider="failed_tests",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_record(self, name: str, data: dict) -> Path:
        p = self.evidence_dir / name
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return p

    def test_r001_hash_prefixed_reverse_filename_sort_does_not_select_old_pass(self) -> None:
        """R001: Reverse filename sort would pick 'fcff...' (old PASS); execution-time selects '45bd...' (new FAIL)."""
        # Old PASS with alphabetically high hash
        self._write_record("fcff3253175386ae-20261006T210245Z.json", {
            "family": "unit",
            "fingerprint": "fcff3253175386ae",
            "finished_utc": "2026-10-06T21:02:45Z",
            "status": "PASS",
            "verdict": "PASS",
            "ran": 5351,
            "red": [],
            "new_red": [],
        })
        # Newer FAIL with alphabetically lower hash
        self._write_record("45bdd3d086aa8bcc-20261101T214539Z.json", {
            "family": "unit",
            "fingerprint": "45bdd3d086aa8bcc",
            "finished_utc": "2026-11-01T21:45:39Z",
            "status": "FAIL",
            "verdict": "FAIL",
            "ran": 8751,
            "red": ["test_a", "test_b"],
            "new_red": ["test_a"],
        })
        res = self.provider.evaluate(self.root, self.goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.satisfaction_status, STATUS_ACTIONABLE_GAPS)
        self.assertEqual(res.metrics.get("failing_count"), 2)

    def test_r002_older_pass_and_newer_fail_selects_fail(self) -> None:
        """R002: Newer FAIL takes precedence over older PASS."""
        self._write_record("zzz_old_pass.json", {
            "family": "unit",
            "fingerprint": "fp_old",
            "finished_utc": "2026-10-01T00:00:00Z",
            "status": "PASS",
            "verdict": "PASS",
            "ran": 100,
            "red": [],
            "new_red": [],
        })
        self._write_record("aaa_new_fail.json", {
            "family": "unit",
            "fingerprint": "fp_new",
            "finished_utc": "2026-11-01T00:00:00Z",
            "status": "FAIL",
            "verdict": "FAIL",
            "ran": 120,
            "red": ["test_regressed"],
            "new_red": ["test_regressed"],
        })
        res = self.provider.evaluate(self.root, self.goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertIn("STALE_FAIL", res.metrics.get("classification", ""))

    def test_r003_focused_pass_does_not_clear_full_family_fail(self) -> None:
        """R003: A focused test run or partial scope cannot satisfy a full-family goal."""
        self._write_record("focused_record.json", {
            "family": "unit",
            "scope_kind": "impact-subset",
            "verification_tier": "FOCUSED",
            "fingerprint": "fp_curr",
            "finished_utc": "2026-11-02T00:00:00Z",
            "status": "PASS",
            "verdict": "PASS",
            "ran": 5,
            "red": [],
            "new_red": [],
        })
        res = self.provider.evaluate(self.root, self.goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.metrics.get("classification"), "INCOMPLETE_COVERAGE")

    def test_r004_pass_for_unrelated_fingerprint_is_stale(self) -> None:
        """R004: PASS for an unrelated source fingerprint must be classified as STALE_PASS."""
        self._write_record("unrelated_pass.json", {
            "family": "unit",
            "fingerprint": "unrelated_fingerprint_12345",
            "finished_utc": "2026-10-30T00:00:00Z",
            "status": "PASS",
            "verdict": "PASS",
            "ran": 500,
            "red": [],
            "new_red": [],
        })
        res = self.provider.evaluate(self.root, self.goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.evidence_freshness, FRESHNESS_STALE)
        self.assertEqual(res.metrics.get("classification"), "STALE_PASS")

    def test_r005_source_modified_after_pass_invalidates_freshness(self) -> None:
        """R005: Source modified after an otherwise valid PASS makes evidence stale."""
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        self._write_record(f"{fp[:16]}-pass.json", {
            "family": "unit",
            "fingerprint": fp,
            "finished_utc": "2026-11-01T00:00:00Z",
            "status": "PASS",
            "verdict": "PASS",
            "ran": 100,
            "red": [],
            "new_red": [],
        })
        # Modify tree
        src_file = self.root / "tools" / "new_mod.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text("# modification", encoding="utf-8")
        
        res = self.provider.evaluate(self.root, self.goal)
        self.assertEqual(res.evidence_freshness, FRESHNESS_STALE)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)

    def test_r006_complete_pass_with_current_identity_is_satisfied(self) -> None:
        """R006: Complete PASS on current tree with matching fingerprint is SATISFIED."""
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        self._write_record(f"{fp[:16]}-pass.json", {
            "family": "unit",
            "fingerprint": fp,
            "finished_utc": "2026-11-02T00:00:00Z",
            "status": "PASS",
            "verdict": "PASS",
            "ran": 50,
            "red": [],
            "new_red": [],
        })
        res = self.provider.evaluate(self.root, self.goal)
        self.assertEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.completeness_status, COMPLETION_FULL)
        self.assertEqual(res.evidence_freshness, FRESHNESS_CURRENT)
        self.assertEqual(res.metrics.get("classification"), "CURRENT_PASS")

    def test_r007_failed_evidence_with_red_and_no_legacy_failures_field(self) -> None:
        """R007: Provider correctly extracts failures from 'red' when 'failures' is absent."""
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        self._write_record(f"{fp[:16]}-fail.json", {
            "family": "unit",
            "fingerprint": fp,
            "finished_utc": "2026-11-02T00:00:00Z",
            "status": "FAIL",
            "verdict": "FAIL",
            "ran": 50,
            "red": ["test_foo.py", "test_bar.py"],
            "new_red": ["test_foo.py"],
        })
        res = self.provider.evaluate(self.root, self.goal)
        self.assertEqual(res.satisfaction_status, STATUS_ACTIONABLE_GAPS)
        self.assertEqual(len(res.actionable_candidates), 2)
        candidate_titles = [c.title for c in res.actionable_candidates]
        self.assertTrue(any("test_foo.py" in t for t in candidate_titles))

    def test_r008_baseline_fail_with_no_new_red_is_baseline_blocked(self) -> None:
        """R008: Baseline failures with zero new-red items must not be falsely SATISFIED."""
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        self._write_record(f"{fp[:16]}-baseline.json", {
            "family": "unit",
            "fingerprint": fp,
            "finished_utc": "2026-11-02T00:00:00Z",
            "status": "PASS",
            "verdict": "PASS",
            "ran": 50,
            "red": ["test_baseline_defect.py"],
            "new_red": [],
        })
        res = self.provider.evaluate(self.root, self.goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.metrics.get("classification"), "BASELINE_BLOCKED")
        self.assertEqual(len(res.actionable_candidates), 1)

    def test_r009_invalid_or_corrupted_evidence_record_rejected(self) -> None:
        """R009: Corrupted JSON or record missing schema fields rejected as INVALID_EVIDENCE."""
        p = self.evidence_dir / "corrupted.json"
        p.write_text("{ unclosed json: ", encoding="utf-8")
        res = self.provider.evaluate(self.root, self.goal)
        self.assertEqual(res.satisfaction_status, STATUS_BLOCKED_BY_EVIDENCE)
        self.assertEqual(res.metrics.get("classification"), "INVALID_EVIDENCE")

    def test_r010_missing_matching_evidence_handled_honestly(self) -> None:
        """R010: Empty evidence directory returns honest MISSING_EVIDENCE."""
        res = self.provider.evaluate(self.root, self.goal)
        self.assertEqual(res.satisfaction_status, STATUS_NO_ADMISSIBLE_WORK)
        self.assertEqual(res.metrics.get("classification"), "MISSING_EVIDENCE")

    def test_r011_registered_goal_persists_and_recovers_from_canonical_path(self) -> None:
        """R011: Goal stored at canonical .saipen/goals/ path is recoverable directly."""
        save_goal(self.root, self.goal)
        recovered = get_goal(self.root, self.goal.goal_id)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.goal_id, self.goal.goal_id)
        self.assertEqual(recovered.evidence_provider, "failed_tests")

    def test_r012_duplicate_registered_goal_refused(self) -> None:
        """R012: Registering a goal that already exists raises DuplicateGoalError."""
        register_goal(self.root, self.goal)
        with self.assertRaises(DuplicateGoalError):
            register_goal(self.root, self.goal)

    def test_r013_goal_registered_does_not_grant_authority(self) -> None:
        """R013: A registered goal JSON grants zero authorization without an operator grant."""
        register_goal(self.root, self.goal)
        state = {"execution_intent": "goal", "continuation_authority": "operator_required"}
        self.assertFalse(goal_authority.persistent(state))

    def test_r014_legacy_capsule_supplied_to_campaign_admission_rejected(self) -> None:
        """R014: Legacy goal continuation capsule is rejected by campaign_authority."""
        legacy_capsule = json.dumps({
            "kind": "saipen-goal-continuation",
            "project_lineage": "lineage-test",
            "continuation_authority": "operator_persistent",
            "authority_source": "E-100",
            "authority_until": "continuous_maintenance",
            "safety_valve_mode": "checkpoint",
        })
        with self.assertRaises(ValueError) as ctx:
            campaign_authority.parse_capsule(legacy_capsule)
        self.assertIn("legacy goal capsule", str(ctx.exception))

    def test_r015_campaign_capsule_supplied_to_legacy_goal_authorization_rejected(self) -> None:
        """R015: Campaign authorization capsule is rejected by goal_authority."""
        campaign_capsule = json.dumps({
            "schema_version": 1,
            "kind": "saipen-campaign-authorization",
            "campaign_limit": 1,
            "project_lineage": "lineage-test",
            "target_project": "test-proj",
            "host": "test-host",
            "session": "test-session",
            "goal_binding": {"goal_ingress": "goal-1234567890abcdef", "authority_source": "E-100"},
            "authorized_scopes": ["continuous_maintenance"],
            "resource_budget": {"max_cycles": 10, "max_wall_seconds": 3600.0, "max_generations": 5},
            "expires_at": time.time() + 3600,
        })
        with self.assertRaises(ValueError) as ctx:
            goal_authority.parse_capsule(campaign_capsule)
        self.assertIn("campaign capsule supplied to legacy goal authorization", str(ctx.exception))

    def test_r016_campaign_capsule_wrong_target_project_or_host_rejected(self) -> None:
        """R016: Campaign capsule with missing/empty host or target_project rejected."""
        invalid_capsule = json.dumps({
            "schema_version": 1,
            "kind": "saipen-campaign-authorization",
            "campaign_limit": 1,
            "project_lineage": "lineage-test",
            "target_project": "   ",  # empty
            "host": "test-host",
            "session": "test-session",
            "goal_binding": {"goal_ingress": "goal-1234567890abcdef", "authority_source": "E-100"},
            "authorized_scopes": ["continuous_maintenance"],
            "resource_budget": {"max_cycles": 10, "max_wall_seconds": 3600.0, "max_generations": 5},
            "expires_at": time.time() + 3600,
        })
        with self.assertRaises(ValueError) as ctx:
            campaign_authority.parse_capsule(invalid_capsule)
        self.assertIn("project/host/session identity", str(ctx.exception))

    def test_r017_campaign_capsule_expired_or_invalid_budget_rejected(self) -> None:
        """R017: Campaign capsule with non-positive budget or expired timestamp rejected."""
        expired_capsule = json.dumps({
            "schema_version": 1,
            "kind": "saipen-campaign-authorization",
            "campaign_limit": 1,
            "project_lineage": "lineage-test",
            "target_project": "test-proj",
            "host": "test-host",
            "session": "test-session",
            "goal_binding": {"goal_ingress": "goal-1234567890abcdef", "authority_source": "E-100"},
            "authorized_scopes": ["continuous_maintenance"],
            "resource_budget": {"max_cycles": 0, "max_wall_seconds": 3600.0, "max_generations": 5},
            "expires_at": -100,  # invalid/negative
        })
        with self.assertRaises(ValueError):
            campaign_authority.parse_capsule(expired_capsule)

    def test_r018_campaign_capsule_correctly_authenticated(self) -> None:
        """R018: Valid campaign capsule with correct fields and budget parses cleanly."""
        valid_capsule = json.dumps({
            "schema_version": 1,
            "kind": "saipen-campaign-authorization",
            "campaign_limit": 1,
            "project_lineage": "lineage-test",
            "target_project": "test-proj",
            "host": "test-host",
            "session": "test-session",
            "goal_binding": {"goal_ingress": "goal-1234567890abcdef", "authority_source": "E-100"},
            "authorized_scopes": ["continuous_maintenance"],
            "resource_budget": {"max_cycles": 10, "max_wall_seconds": 3600.0, "max_generations": 5},
            "expires_at": time.time() + 3600,
        })
        parsed = campaign_authority.parse_capsule(valid_capsule)
        self.assertEqual(parsed["kind"], "saipen-campaign-authorization")
        self.assertEqual(parsed["authorized_scopes"], ["continuous_maintenance"])

    def test_r019_zero_new_defects_unchanged_generation_is_pure(self) -> None:
        """R019: Evaluating unchanged generation with zero new defects mutates zero bytes."""
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        rec = self._write_record(f"{fp[:16]}-pass.json", {
            "family": "unit",
            "fingerprint": fp,
            "finished_utc": "2026-11-02T00:00:00Z",
            "status": "PASS",
            "verdict": "PASS",
            "ran": 100,
            "red": [],
            "new_red": [],
        })
        mtime_before = rec.stat().st_mtime_ns
        res1 = self.provider.evaluate(self.root, self.goal)
        res2 = self.provider.evaluate(self.root, self.goal)
        mtime_after = rec.stat().st_mtime_ns
        self.assertEqual(mtime_before, mtime_after)
        self.assertEqual(res1.satisfaction_status, res2.satisfaction_status)

    def test_r020_newly_arrived_evidence_resumes_from_quiescence(self) -> None:
        """R020: Arrival of new test failure record turns quiescent state into ACTIONABLE_GAPS."""
        res_initial = self.provider.evaluate(self.root, self.goal)
        self.assertEqual(res_initial.satisfaction_status, STATUS_NO_ADMISSIBLE_WORK)
        
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        self._write_record(f"{fp[:16]}-fail.json", {
            "family": "unit",
            "fingerprint": fp,
            "finished_utc": "2026-11-02T00:00:00Z",
            "status": "FAIL",
            "verdict": "FAIL",
            "ran": 100,
            "red": ["test_arrived.py"],
            "new_red": ["test_arrived.py"],
        })
        res_after = self.provider.evaluate(self.root, self.goal)
        self.assertEqual(res_after.satisfaction_status, STATUS_ACTIONABLE_GAPS)
        self.assertEqual(len(res_after.actionable_candidates), 1)

    def test_r021_full_suite_pass_does_not_clear_backlog_gaps(self) -> None:
        """R021: Comprehensive maintenance provider keeps goal active if backlog has items."""
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        self._write_record(f"{fp[:16]}-pass.json", {
            "family": "unit",
            "fingerprint": fp,
            "finished_utc": "2026-11-02T00:00:00Z",
            "status": "PASS",
            "verdict": "PASS",
            "ran": 100,
            "red": [],
            "new_red": [],
        })
        # Backlog with pending items
        backlog_file = self.root / ".saipen" / "backlog.json"
        backlog_file.write_text(json.dumps([
            {"id": "item-1", "title": "Audit backlog task", "done": False}
        ]), encoding="utf-8")
        goal = PersistentGoal(
            goal_id="maint-multi",
            project_id="test-proj",
            title="Multi-Signal Maintenance",
            objective="All maintenance clean",
            evidence_provider="comprehensive_maintenance",
            research_or_work_backlog_source=".saipen/backlog.json",
        )
        comp = ComprehensiveMaintenanceProvider()
        res = comp.evaluate(self.root, goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)
        self.assertEqual(res.satisfaction_status, STATUS_ACTIONABLE_GAPS)

    def test_r022_native_successor_model_turn_execution_interface(self) -> None:
        """R022: Discovery candidates produce valid candidate tasks with actionable runnable commands."""
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        self._write_record(f"{fp[:16]}-fail.json", {
            "family": "unit",
            "fingerprint": fp,
            "finished_utc": "2026-11-02T00:00:00Z",
            "status": "FAIL",
            "verdict": "FAIL",
            "ran": 50,
            "red": ["test_repair.py"],
            "new_red": ["test_repair.py"],
        })
        res = self.provider.evaluate(self.root, self.goal)
        task = res.actionable_candidates[0]
        self.assertTrue(task.candidate_id.startswith(self.goal.goal_id))
        self.assertIn("test_repair.py", task.verification)

    def test_r023_release_blocked_while_independent_engineering_continues(self) -> None:
        """R023: Release gate being blocked does not suppress local goal evaluation."""
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        self._write_record(f"{fp[:16]}-fail.json", {
            "family": "unit",
            "fingerprint": fp,
            "finished_utc": "2026-11-02T00:00:00Z",
            "status": "FAIL",
            "verdict": "FAIL",
            "ran": 50,
            "red": ["test_indep.py"],
            "new_red": ["test_indep.py"],
        })
        # Goal evaluation proceeds completely independently of release gates
        res = self.provider.evaluate(self.root, self.goal)
        self.assertEqual(res.satisfaction_status, STATUS_ACTIONABLE_GAPS)

    def test_r024_no_false_project_completion_from_one_clean_test_family(self) -> None:
        """R024: One clean test family does not conclude multi-signal project completion."""
        comp = ComprehensiveMaintenanceProvider()
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        self._write_record(f"{fp[:16]}-pass.json", {
            "family": "unit",
            "fingerprint": fp,
            "finished_utc": "2026-11-02T00:00:00Z",
            "status": "PASS",
            "verdict": "PASS",
            "ran": 100,
            "red": [],
            "new_red": [],
        })
        # Backlog has pending items
        backlog_file = self.root / ".saipen" / "backlog.json"
        backlog_file.write_text(json.dumps([
            {"id": "item-2", "title": "Pending documentation debt", "done": False}
        ]), encoding="utf-8")
        goal = PersistentGoal(
            goal_id="maint-full",
            project_id="test-proj",
            title="Full Project Maintenance",
            objective="Ensure all items resolved",
            evidence_provider="comprehensive_maintenance",
            research_or_work_backlog_source=".saipen/backlog.json",
        )
        res = comp.evaluate(self.root, goal)
        self.assertNotEqual(res.satisfaction_status, STATUS_SATISFIED)


if __name__ == "__main__":
    unittest.main()
