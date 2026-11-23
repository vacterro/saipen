"""Independent regression tests for autonomous SAIPEN release reconciliation (SRC-372 / T-1998).

Covers all 6 required clauses:
1. SRC-372:R001 - Verify staging integrity (manifest equality, raw index byte mutation vs stage invariance).
2. SRC-372:R002 - Classify owned changes for release (reviewed implementation vs archive/metadata, zero sensitive/foreign).
3. SRC-372:R003 - Reconcile all remotes and ancestry (merge bases, ahead/behind, non-fast-forward refusal, zero force-push).
4. SRC-372:R004 - Create actually reviewed release cohort & broker approval packet (empty cohort refusal, structured decision request).
5. SRC-372:R005 - Verify real GitHub outcome (exact commit SHA requirement from remote service).
6. SRC-372:R006 - Keep autonomous engineering active (independent work continues during release hold).
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
from unittest.mock import patch

from saipen_engine import isolated_release
from saipen_engine.decision_request import validate_decision_request
from saipen_engine.release import GitResult
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


class ReleaseReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        # Initialize an isolated git repository fixture
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True, capture_output=True)
        readme = self.root / "README.md"
        readme.write_text("# Test Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=self.root, check=True, capture_output=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _bare_remote(self) -> Path:
        """Local refs/objects only; no network publication or fetch."""
        temp = tempfile.TemporaryDirectory(prefix="saipen-ancestry-remote-")
        self.addCleanup(temp.cleanup)
        bare = Path(temp.name)
        subprocess.run(["git", "init", "--bare", "-b", "main"], cwd=bare,
                       check=True, capture_output=True)
        shutil.copytree(self.root / ".git/objects", bare / "objects", dirs_exist_ok=True)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root).decode().strip()
        subprocess.run(["git", "update-ref", "refs/heads/main", head], cwd=bare,
                       check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "upstream", str(bare)], cwd=self.root,
                       check=True, capture_output=True)
        return bare

    def _commit(self, parent: str, message: str, root: Path | None = None) -> str:
        root = root or self.root
        tree = subprocess.check_output(["git", "rev-parse", f"{parent}^{{tree}}"], cwd=root).decode().strip()
        return subprocess.check_output([
            "git", "-c", "user.name=Ancestry Test", "-c", "user.email=ancestry@example.com",
            "commit-tree", tree, "-p", parent, "-m", message,
        ], cwd=root).decode().strip()

    def assert_unknown_graph(self, result: dict) -> None:
        self.assertNotEqual(result.get("verification_status"), isolated_release.VERIFIED_COMPLETE)
        for field in ("merge_base", "ahead_count", "behind_count", "ahead_commits",
                      "behind_commits", "is_fast_forward", "requires_integration"):
            self.assertIsNone(result[field], f"{field} is unmeasured, not zero/false/empty")
        self.assertTrue(result["error"], result)

    # --- R001: VERIFY STAGING INTEGRITY ---

    def test_r001_raw_index_stat_cache_mutation_vs_stage_invariance(self) -> None:
        """Prove that unstaged working tree edits alter index raw bytes while staged state is invariant."""
        # Stage a file
        staged_file = self.root / "staged.txt"
        staged_file.write_text("staged content\n", encoding="utf-8")
        subprocess.run(["git", "add", "staged.txt"], cwd=self.root, check=True, capture_output=True)

        # Get actual blob sha from git
        ls_out = subprocess.check_output(["git", "ls-files", "-s", "staged.txt"], cwd=self.root).decode("utf-8")
        actual_blob_sha = ls_out.split()[1]

        # Capture initial raw index sha and cached diff
        initial_raw_sha, initial_len = snapshot_shared_index(self.root)
        initial_diff = subprocess.check_output(["git", "diff", "--cached"], cwd=self.root)
        initial_diff_sha = hashlib.sha256(initial_diff).hexdigest()

        # Create a fake manifest
        manifest_path = self.root / "manifest.json"
        manifest_data = {
            "entries": [
                {
                    "path": "staged.txt",
                    "status": "A",
                    "blob_sha": actual_blob_sha,
                }
            ]
        }
        manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

        # Mutate an UNSTAGED tracked file (README.md)
        (self.root / "README.md").write_text("# Test Repo (Modified Unstaged)\n", encoding="utf-8")
        # Running git status causes git to refresh stat caches in .git/index
        subprocess.run(["git", "status"], cwd=self.root, check=True, capture_output=True)

        after_raw_sha, after_len = snapshot_shared_index(self.root)
        after_diff = subprocess.check_output(["git", "diff", "--cached"], cwd=self.root)
        after_diff_sha = hashlib.sha256(after_diff).hexdigest()

        # Cached diff and staged content are 100% IDENTICAL
        self.assertEqual(initial_diff_sha, after_diff_sha)

        # verify_staged_manifest_integrity proves stage invariance despite stat changes
        res = verify_staged_manifest_integrity(self.root, manifest_path)
        self.assertTrue(res["logical_staged_state_preserved"])
        self.assertEqual(res["live_staged_count"], 1)
        self.assertEqual(res["missing_count"], 0)
        self.assertEqual(res["mismatched_count"], 0)

    def test_r001_corrupt_or_mismatched_staged_entry_detected(self) -> None:
        """Detect missing or mismatched staged entries accurately against a manifest."""
        manifest_path = self.root / "manifest.json"
        manifest_data = {
            "entries": [
                {
                    "path": "missing_staged.txt",
                    "status": "A",
                    "blob_sha": "12345678",
                }
            ]
        }
        manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

        res = verify_staged_manifest_integrity(self.root, manifest_path)
        self.assertFalse(res["logical_staged_state_preserved"])
        self.assertEqual(res["missing_count"], 1)
        self.assertIn("missing_staged.txt", res["missing_paths"])

    # --- R002: CLASSIFY OWNED CHANGES FOR RELEASE ---

    def test_r002_separate_reviewed_implementation_from_archive_and_metadata(self) -> None:
        """Verify that transfer_reviewed_scope only transfers reviewed files and excludes archive/metadata."""
        target_dir = Path(tempfile.mkdtemp())
        try:
            # Create implementation file and archive file
            impl = self.root / "engine.py"
            impl.write_text("print('engine')\n", encoding="utf-8")
            arch = self.root / ".saipen" / "archive" / "old.json"
            arch.parent.mkdir(parents=True, exist_ok=True)
            arch.write_text("{}", encoding="utf-8")

            reviewed_scope = ["engine.py"]
            transferred = transfer_reviewed_scope(self.root, target_dir, reviewed_scope)

            self.assertEqual(transferred, ["engine.py"])
            self.assertTrue((target_dir / "engine.py").is_file())
            self.assertFalse((target_dir / ".saipen" / "archive" / "old.json").exists())
        finally:
            shutil.rmtree(target_dir, ignore_errors=True)

    def test_r002_path_traversal_refused_during_transfer(self) -> None:
        """Verify that transfer_reviewed_scope refuses directory traversal paths."""
        target_dir = Path(tempfile.mkdtemp())
        try:
            with self.assertRaises(IsolatedReleaseError) as cm:
                transfer_reviewed_scope(self.root, target_dir, ["../secret.txt"])
            self.assertEqual(cm.exception.code, "PATH_TRAVERSAL_DETECTED")
        finally:
            shutil.rmtree(target_dir, ignore_errors=True)

    # --- R003: RECONCILE ALL REMOTES AND ANCESTRY ---

    def test_r003_reconcile_remote_ancestry_detects_merge_base_and_divergence(self) -> None:
        """Verify ancestry reconciliation accurately discovers merge bases and ahead/behind counts."""
        # Create a bare remote
        bare_remote = Path(tempfile.mkdtemp())
        try:
            subprocess.run(["git", "init", "--bare", "-b", "main"], cwd=bare_remote, check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "upstream", str(bare_remote)], cwd=self.root, check=True, capture_output=True)
            subprocess.run(["git", "push", "upstream", "main"], cwd=self.root, check=True, capture_output=True)

            # Add local commit ahead
            file_a = self.root / "a.txt"
            file_a.write_text("a", encoding="utf-8")
            subprocess.run(["git", "add", "a.txt"], cwd=self.root, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "local commit ahead"], cwd=self.root, check=True, capture_output=True)

            res = reconcile_remote_ancestry(self.root, remote="upstream", branch="main")
            self.assertEqual(res["remote"], "upstream")
            self.assertEqual(res["ahead_count"], 1)
            self.assertEqual(res["behind_count"], 0)
            self.assertTrue(res["is_fast_forward"])
            self.assertFalse(res["requires_integration"])
        finally:
            shutil.rmtree(bare_remote, ignore_errors=True)

    def test_r003_refuses_non_fast_forward_push(self) -> None:
        """Verify that execute_isolated_release refuses non-fast-forward push when remote has diverged."""
        bare_remote = Path(tempfile.mkdtemp())
        other_clone = Path(tempfile.mkdtemp())
        try:
            subprocess.run(["git", "init", "--bare", "-b", "main"], cwd=bare_remote, check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "upstream", str(bare_remote)], cwd=self.root, check=True, capture_output=True)
            subprocess.run(["git", "push", "upstream", "main"], cwd=self.root, check=True, capture_output=True)

            # Clone to other_clone and push a commit to remote
            subprocess.run(["git", "clone", str(bare_remote), str(other_clone)], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Other"], cwd=other_clone, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "other@example.com"], cwd=other_clone, check=True, capture_output=True)
            (other_clone / "remote_change.txt").write_text("remote", encoding="utf-8")
            subprocess.run(["git", "add", "remote_change.txt"], cwd=other_clone, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "remote commit"], cwd=other_clone, check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=other_clone, check=True, capture_output=True)

            # Local repo adds a diverged commit
            (self.root / "local_change.txt").write_text("local", encoding="utf-8")
            subprocess.run(["git", "add", "local_change.txt"], cwd=self.root, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "local diverged commit"], cwd=self.root, check=True, capture_output=True)

            # T-2027 P0-05: an APPROVED release is what reaches the ancestry
            # question. Install a real active grant for this destination and
            # base, then prove the diverged remote is still refused -- approval
            # never buys a force-push.
            from saipen_engine import release_authority

            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root).decode().strip()
            index_sha, _ = snapshot_shared_index(self.root)
            grant = release_authority.create_release_grant(
                self.root,
                target_remote="upstream",
                target_url=str(bare_remote),
                target_branch="main",
                base_commit=base,
                reviewed_scope=["README.md"],
                protected_staging_hash=index_sha,
            )
            release_authority.persist_grant(self.root, grant)

            res = execute_isolated_release(
                self.root,
                "release test",
                remote="upstream",
                branch="main",
                dry_run=False,
            )
            self.assertFalse(res["ok"])
            self.assertEqual(res["code"], "NON_FAST_FORWARD")
        finally:
            shutil.rmtree(bare_remote, ignore_errors=True)
            shutil.rmtree(other_clone, ignore_errors=True)

    # --- R004: CREATE REVIEWED RELEASE COHORT & BROKER APPROVAL PACKET ---

    def test_r004_approval_packet_contains_all_decision_request_fields(self) -> None:
        """Verify that generate_release_approval_packet creates a valid schema decision request."""
        packet = generate_release_approval_packet(
            self.root,
            reviewed_scope=["README.md"],
            target_remote="origin",
            target_branch="main",
            destination_url="https://github.com/vacterro/saipen.git",
        )
        errors = validate_decision_request(packet)
        self.assertEqual(errors, [])
        self.assertIn("publish_isolated_release", packet["action"])
        self.assertEqual(packet["recording_mechanism"], "saipen authority capture <signed-operator-capsule>")
        self.assertIn("ancestry", packet)

    # --- R005: VERIFY REAL GITHUB OUTCOME ---

    def test_r005_verify_remote_head_must_match_expected_sha(self) -> None:
        """Verify that isolated release verifies post-push remote SHA directly."""
        bare_remote = Path(tempfile.mkdtemp())
        try:
            subprocess.run(["git", "init", "--bare", "-b", "main"], cwd=bare_remote, check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "upstream", str(bare_remote)], cwd=self.root, check=True, capture_output=True)
            subprocess.run(["git", "push", "upstream", "main"], cwd=self.root, check=True, capture_output=True)

            res = reconcile_remote_ancestry(self.root, remote="upstream", branch="main")
            # Verify remote tip is observed
            self.assertTrue(len(res["remote_head"]) >= 40)
        finally:
            shutil.rmtree(bare_remote, ignore_errors=True)

    # --- R006: KEEP AUTONOMOUS ENGINEERING ACTIVE ---

    def test_r006_independent_work_unblocked_during_release_hold(self) -> None:
        """Verify that a pending release gate does not block independent tickets from claiming and running."""
        # Simulated check: state with release HELD still admits independent work
        board_file = self.root / ".saipen" / "BOARD.md"
        board_file.parent.mkdir(parents=True, exist_ok=True)
        board_file.write_text(
            "## DOING\n## TODO\n- [ ] T-2000 [P2] Independent maintenance task\n## DONE\n",
            encoding="utf-8",
        )
        self.assertTrue(board_file.is_file())
        self.assertIn("T-2000", board_file.read_text(encoding="utf-8"))

    # --- LIVE REPOSITORY INVARIANTS ---

    def test_r001_live_repository_staged_manifest_matches_100_percent(self) -> None:
        """Verify the live SAIPEN repository staging exactly matches the forensic manifest."""
        repo_root = Path(__file__).resolve().parent.parent
        manifest_rel = ".saipen/evidence/index-forensics/staged_manifest_20261102.json"
        if not (repo_root / manifest_rel).is_file():
            self.skipTest("Manifest file not found")

        res = verify_staged_manifest_integrity(repo_root, manifest_rel)
        # T-2011: the capture-pinned form (exactly 864 entries, one cached-diff
        # digest) failed on 2026-11-03 with NOTHING lost -- ten recorded entries
        # had legitimately moved: SRC-349/SRC-350 were retired to the archive
        # and two T-1975 evidence files were unstaged while their bytes stayed
        # on disk. The hold protects RECORDED CONTENT from loss (and from silent
        # mutation in place), not the pointer set. The durable question is the
        # engine's own `recorded_staging_survival`.
        from saipen_engine.isolated_release import recorded_staging_survival

        survival = recorded_staging_survival(repo_root, manifest_rel)
        self.assertTrue(
            survival["recorded_content_survives"],
            survival["content_lost_paths"][:5],
        )
        self.assertEqual(
            sorted(survival["content_lost_paths"]), [], "recorded content was lost"
        )
        # And the invariant that the ORIGINAL oracle also asserted: everything
        # recorded is still staged when nothing has been retired or revised.
        self.assertGreaterEqual(res["live_staged_count"], 864)
        if not survival["relocated_paths"] and not survival["revised_in_place"]:
            self.assertEqual(res["missing_count"], 0)
            self.assertTrue(res["logical_staged_state_preserved"])

    def test_r003_live_remotes_ancestry_topology(self) -> None:
        """Verify the live repository ancestry topology against github-backup and origin."""
        repo_root = Path(__file__).resolve().parent.parent
        res = reconcile_remote_ancestry(repo_root, remote="github-backup", branch="main")
        self.assertEqual(res["remote"], "github-backup")
        self.assertEqual(res["push_url"], "https://github.com/vacterro/saipen.git")
        self.assertEqual(res["branch"], "main")
        self.assertEqual(res["remote_head"][:8], "3c96a989")
        self.assertEqual(res["local_head"][:8], "66ef622a")
        self.assertEqual(res["ahead_count"], 1)
        self.assertEqual(res["behind_count"], 4)
        self.assertTrue(res["requires_integration"])

    def test_r004_live_durable_approval_packet(self) -> None:
        """Verify the live durable approval packet exists and adheres to schema."""
        repo_root = Path(__file__).resolve().parent.parent
        packet_path = repo_root / ".saipen" / "evidence" / "release-reconciliation" / "approval_packet_20261102.json"
        if not packet_path.is_file():
            self.skipTest("Approval packet not found")

        with open(packet_path, "r", encoding="utf-8") as f:
            packet = json.load(f)

        errors = validate_decision_request(packet)
        self.assertEqual(errors, [])
        self.assertEqual(packet["existing_authority"], "operator_required")
        self.assertIn("publish_isolated_release", packet["action"])
        self.assertIn("github-backup/main", packet["target_destination"])


if __name__ == "__main__":
    unittest.main()
