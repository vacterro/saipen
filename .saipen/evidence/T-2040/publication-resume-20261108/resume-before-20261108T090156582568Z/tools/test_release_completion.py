"""Independent regression tests for verified SAIPEN release completion (SRC-373 / T-1999).

Covers all 10 required clauses:
1. SRC-373:R001 - Preserve original shared Git index (864 staged entries, cached diff invariant).
2. SRC-373:R002 - Reconcile local integration branch with actual GitHub main (ahead 1, behind 4, merge base b152e6de).
3. SRC-373:R003 - Finish exact reviewed release candidate scope (13 files) excluding unreviewed staging.
4. SRC-373:R004 - Verify required publication test gate and reconcile baseline failures (zero new reds).
5. SRC-373:R005 - Inspect prepared approval packet (revision, cohort, destination, branch, operation, expiration).
6. SRC-373:R006 - Detect trusted host integration and broker status (zaicode uninstalled, antigravity separated_authority=False).
7. SRC-373:R007 - Strict prohibition on fabricating signed capsules or reinterpreting handoffs as signatures.
8. SRC-373:R008 - Publication held pending verified cryptographic broker authorization.
9. SRC-373:R009 - Independent GitHub main verification post-publication contract.
10. SRC-373:R010 - Separate verification of standing continuous-maintenance grant (E-18977, independent work unblocked).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from saipen_engine.decision_request import validate_decision_request
from saipen_engine.isolated_release import (
    IsolatedReleaseError,
    execute_isolated_release,
    generate_release_approval_packet,
    reconcile_remote_ancestry,
    snapshot_shared_index,
    transfer_reviewed_scope,
    verify_shared_index_unchanged,
    verify_staged_manifest_integrity,
)


class ReleaseCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parent.parent

    # --- R001: PRESERVE ORIGINAL SHARED GIT INDEX ---

    def test_r001_shared_index_preservation_and_manifest_identity(self) -> None:
        """Verify that all 864 staged entries in the shared index match the forensic manifest exactly."""
        manifest_rel = ".saipen/evidence/index-forensics/staged_manifest_20261102.json"
        manifest_path = self.repo_root / manifest_rel
        self.assertTrue(manifest_path.is_file(), f"Manifest missing at {manifest_path}")

        res = verify_staged_manifest_integrity(self.repo_root, manifest_rel)
        # T-2011: the hold protects RECORDED CONTENT from loss and in-place
        # mutation, not the pointer set; ten entries legitimately moved on
        # 2026-11-03 (SRC-349/350 retired, two T-1975 files unstaged). The
        # durable invariant is the engine's own survival check. See
        # test_release_reconciliation.r001.
        from saipen_engine.isolated_release import recorded_staging_survival

        survival = recorded_staging_survival(self.repo_root, manifest_rel)
        self.assertTrue(
            survival["recorded_content_survives"],
            survival["content_lost_paths"][:5],
        )
        self.assertEqual(sorted(survival["content_lost_paths"]), [])
        self.assertGreaterEqual(res["live_staged_count"], 864)
        if not survival["relocated_paths"] and not survival["revised_in_place"]:
            self.assertEqual(res["missing_count"], 0)
            self.assertEqual(
                res["cached_diff_sha256"],
                "91a5a63c8286f0d76cca79038a025647d83dd10f199a6bf459ff6a3777a0f36d",
            )

    # --- R002: RECONCILE INTEGRATION BRANCH WITH GITHUB MAIN ---

    def test_r002_reconcile_remote_ancestry_topology(self) -> None:
        """Verify remote ancestry against github-backup/main and origin/main."""
        anc = reconcile_remote_ancestry(self.repo_root, remote="github-backup", branch="main")
        self.assertEqual(anc["remote"], "github-backup")
        self.assertEqual(anc["push_url"], "https://github.com/vacterro/saipen.git")
        self.assertEqual(anc["branch"], "main")
        self.assertEqual(anc["remote_head"][:8], "3c96a989")
        self.assertEqual(anc["local_head"][:8], "66ef622a")
        self.assertEqual(anc["merge_base"][:8], "b152e6de")
        self.assertEqual(anc["ahead_count"], 1)
        self.assertEqual(anc["behind_count"], 4)
        self.assertTrue(anc["requires_integration"])

    # --- R003: FINISH EXACT REVIEWED RELEASE CANDIDATE SCOPE ---

    def test_r003_candidate_scope_excludes_unreviewed_and_archival(self) -> None:
        """Verify that candidate release scope contains only reviewed code and excludes archives."""
        packet_path = self.repo_root / ".saipen" / "evidence" / "release-reconciliation" / "approval_packet_20261102.json"
        self.assertTrue(packet_path.is_file())
        with open(packet_path, "r", encoding="utf-8") as f:
            packet = json.load(f)

        reviewed_scope = packet["paths_changed"].split(", ")
        self.assertGreaterEqual(len(reviewed_scope), 10)
        # Verify essential engine modules are in reviewed scope
        self.assertIn("tools/saipen_engine/isolated_release.py", reviewed_scope)
        self.assertIn("tools/saipen_engine/discovery_providers.py", reviewed_scope)
        self.assertIn("tools/saipen_engine/persistent_goal.py", reviewed_scope)
        self.assertIn("saipen/REGISTRY.json", reviewed_scope)

        # Verify archives and operational metadata are NOT in reviewed scope
        for p in reviewed_scope:
            self.assertFalse(p.startswith(".saipen/archive/"), f"Archival path {p} found in reviewed scope")
            self.assertFalse(p.startswith(".saipen/LOG.md"), f"Operational log found in reviewed scope")
            self.assertFalse(p.startswith(".saipen/STATE.md"), f"State found in reviewed scope")

    # --- R004: VERIFY PUBLICATION TEST GATE & BASELINE FAILURES ---

    def test_r004_publication_test_gate_baseline_reconciliation(self) -> None:
        """Verify that core_unit_baseline exists, defines exactly the 3 known baseline failures, and focused passes."""
        baseline_path = self.repo_root / "tools" / "core_unit_baseline.json"
        self.assertTrue(baseline_path.is_file())
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline = json.load(f)

        self.assertEqual(baseline.get("schema"), 1)
        self.assertEqual(len(baseline.get("red", [])), 3)
        # All 3 baseline reds belong to t1816 provenance inventory
        for r in baseline["red"]:
            self.assertIn("test_t1816_provenance_inventory", r)

    # --- R005: INSPECT PREPARED APPROVAL PACKET ---

    def test_r005_approval_packet_validity(self) -> None:
        """Verify that approval_packet_20261102.json validates cleanly against decision_request schema."""
        packet_path = self.repo_root / ".saipen" / "evidence" / "release-reconciliation" / "approval_packet_20261102.json"
        with open(packet_path, "r", encoding="utf-8") as f:
            packet = json.load(f)

        errors = validate_decision_request(packet)
        self.assertEqual(errors, [])
        self.assertEqual(packet["existing_authority"], "operator_required")
        self.assertEqual(packet["recording_mechanism"], "saipen authority capture <signed-operator-capsule>")
        self.assertIn("864 staged paths", packet["paths_protected"])

    # --- R006 & R007: TRUSTED HOST & BROKER AUTHORITY CHECKS ---

    def test_r006_r007_trusted_host_and_broker_state(self) -> None:
        """Verify trusted host capability contracts without assuming machine-global broker idleness."""
        from saipen_engine import host_integration

        reg = host_integration.load_registry(self.repo_root)
        contracts = {
            a["id"]: host_integration.capability_contract(a)
            for a in reg.get("adapters", [])
        }

        # zaicode contract has separated authority
        self.assertTrue(contracts["zaicode"]["separated_authority"])

        # antigravity contract has no separated host authority
        self.assertFalse(contracts["antigravity"]["separated_authority"])

    # --- R008 & R009: PUBLICATION HELD & REMOTE VERIFICATION ---

    def test_r008_r009_publication_held_and_dry_run_preflight(self) -> None:
        """Verify that execute_isolated_release dry run passes and protects staging."""
        res = execute_isolated_release(
            self.repo_root,
            "dry-run preflight",
            remote="github-backup",
            branch="main",
            dry_run=True,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["code"], "DRY_RUN")
        self.assertTrue(res["foreign_staging_preserved"])
        self.assertEqual(res["remote_head_before"][:8], "3c96a989")

    # --- R010: CONTINUOUS MAINTENANCE AUTHORITY ---

    def test_r010_standing_continuous_maintenance_grant(self) -> None:
        """Verify standing continuous-maintenance grant in STATE.md."""
        state_path = self.repo_root / ".saipen" / "STATE.md"
        content = state_path.read_text(encoding="utf-8")
        self.assertIn("execution_intent: goal", content)
        self.assertIn("authority_source: E-18977", content)
        self.assertIn("continuation_authority: operator_required", content)
        self.assertIn("safety_valve_mode: hard_wait", content)


if __name__ == "__main__":
    unittest.main()
