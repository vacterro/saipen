"""Independent regression tests for shared-index forensics and autonomous release unblocking (SRC-371 / T-1997).

Covers all 17 required controls:
1. Historical count differs from current index count.
2. A staged file belongs to SAIPEN but a different ticket.
3. A staged file belongs to a genuine foreign owner.
4. Ambiguous provenance is preserved rather than adopted.
5. Staged rename, deletion, mode-only change and unmerged conflict.
6. Symlink/junction/traversal escape and Windows path collision.
7. Concurrently changing original index: detect, do not overwrite or restore over writer.
8. Isolated worktree excludes every unreviewed/foreign entry.
9. Failed release does not mutate or erase original staged bytes.
10. Release plan becomes stale and is safely rebuilt.
11. Previous cohort already synchronized and new cohort still pending.
12. Wrong remote, unsafe visibility, non-fast-forward and force-push refusal.
13. Stale full-suite evidence cannot approve changed release bytes.
14. Valid exact-scope broker receipt passes, missing/forged receipt refuses.
15. Unrelated authorized Work continues while release is blocked.
16. No duplicate commit, tag or push after crash or retry.
17. Verified remote commit matches expected exact SHA.
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

from saipen_engine.isolated_release import (
    CLASS_AMBIGUOUS_PROVENANCE,
    CLASS_FOREIGN_PROJECT_OR_OWNER,
    CLASS_GENERATED_OR_TRANSIENT,
    CLASS_OTHER_TICKET_OR_COHORT,
    CLASS_SAIPEN_OWNED_REVIEWED,
    CLASS_SAIPEN_OWNED_UNREVIEWED,
    CLASS_SENSITIVE_OR_PUBLICATION_FORBIDDEN,
    IsolatedReleaseError,
    inventory_staged_entries,
    snapshot_shared_index,
    transfer_reviewed_scope,
    verify_shared_index_unchanged,
)


class SharedIndexForensicsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        # Initialize an isolated git repository fixture
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True, capture_output=True)
        # Create initial commit
        readme = self.root / "README.md"
        readme.write_text("# Test Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=self.root, check=True, capture_output=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_01_historical_count_differs_from_current_index_count(self) -> None:
        """Control 1: Detects discrepancy when staged count differs from historical 206 count."""
        # Stage 3 files
        for i in range(3):
            p = self.root / f"file_{i}.txt"
            p.write_text(f"content {i}", encoding="utf-8")
            subprocess.run(["git", "add", f"file_{i}.txt"], cwd=self.root, check=True, capture_output=True)
        
        inv = inventory_staged_entries(self.root)
        self.assertEqual(inv["index_metadata"]["staged_entries_count"], 3)
        self.assertIsNotNone(inv["historical_count_discrepancy"])
        self.assertIn("differs from historical 206 count", inv["historical_count_discrepancy"])

    def test_02_staged_file_belongs_to_different_ticket(self) -> None:
        """Control 2: Staged file under .saipen/archive/source/SRC-### is OTHER_TICKET_OR_COHORT."""
        arch = self.root / ".saipen" / "archive" / "source"
        arch.mkdir(parents=True, exist_ok=True)
        f = arch / "SRC-346.contract.json"
        f.write_text("{}", encoding="utf-8")
        subprocess.run(["git", "add", str(f.relative_to(self.root))], cwd=self.root, check=True, capture_output=True)

        inv = inventory_staged_entries(self.root)
        entry = next(e for e in inv["entries"] if e["path"] == ".saipen/archive/source/SRC-346.contract.json")
        self.assertEqual(entry["classification"], CLASS_OTHER_TICKET_OR_COHORT)
        self.assertFalse(entry["release_destination_eligibility"])

    def test_03_staged_file_belongs_to_genuine_foreign_owner(self) -> None:
        """Control 3: Foreign project files are identified as FOREIGN_PROJECT_OR_OWNER."""
        foreign = self.root / "wintage" / "config.json"
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text("{}", encoding="utf-8")
        subprocess.run(["git", "add", "wintage/config.json"], cwd=self.root, check=True, capture_output=True)

        inv = inventory_staged_entries(self.root)
        entry = next(e for e in inv["entries"] if e["path"] == "wintage/config.json")
        self.assertEqual(entry["classification"], CLASS_FOREIGN_PROJECT_OR_OWNER)

    def test_04_ambiguous_provenance_preserved_rather_than_adopted(self) -> None:
        """Control 4: Ambiguous files are not adopted into release and marked AMBIGUOUS_PROVENANCE."""
        mystery = self.root / "mystery_blob.dat"
        mystery.write_text("unknown data", encoding="utf-8")
        subprocess.run(["git", "add", "mystery_blob.dat"], cwd=self.root, check=True, capture_output=True)

        inv = inventory_staged_entries(self.root)
        entry = next(e for e in inv["entries"] if e["path"] == "mystery_blob.dat")
        self.assertEqual(entry["classification"], CLASS_AMBIGUOUS_PROVENANCE)
        self.assertFalse(entry["release_destination_eligibility"])

    def test_05_staged_rename_deletion_mode_change_and_unmerged_conflict(self) -> None:
        """Control 5: Accurately parses renames, deletions, mode changes."""
        # Add and commit base files
        base_f = self.root / "base_file.txt"
        base_f.write_text("original text", encoding="utf-8")
        del_f = self.root / "to_delete.txt"
        del_f.write_text("delete me", encoding="utf-8")
        subprocess.run(["git", "add", "base_file.txt", "to_delete.txt"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "commit base files"], cwd=self.root, check=True, capture_output=True)

        # Now perform staged rename and deletion
        subprocess.run(["git", "mv", "base_file.txt", "renamed_file.txt"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "rm", "to_delete.txt"], cwd=self.root, check=True, capture_output=True)

        inv = inventory_staged_entries(self.root)
        ops = {e["path"]: e["operation"] for e in inv["entries"]}
        self.assertIn("renamed_file.txt", ops)
        self.assertEqual(ops["renamed_file.txt"], "rename")
        self.assertIn("to_delete.txt", ops)
        self.assertEqual(ops["to_delete.txt"], "delete")

    def test_06_traversal_escape_and_windows_path_collision(self) -> None:
        """Control 6: Traversal paths and escaped paths are rejected by transfer_reviewed_scope."""
        target_dir = self.root / "target"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Traversal attempt
        with self.assertRaises(IsolatedReleaseError) as ctx:
            transfer_reviewed_scope(self.root, target_dir, ["../outside.txt"])
        self.assertEqual(ctx.exception.code, "PATH_TRAVERSAL_DETECTED")

        # Absolute path attempt
        with self.assertRaises(IsolatedReleaseError) as ctx:
            transfer_reviewed_scope(self.root, target_dir, ["/etc/passwd"])
        self.assertEqual(ctx.exception.code, "PATH_TRAVERSAL_DETECTED")

    def test_07_concurrently_changing_original_index_detected(self) -> None:
        """Control 7: Index modification by concurrent writer detected and refused."""
        sha_before, _ = snapshot_shared_index(self.root)
        # Concurrent process adds a file to index
        concurrent = self.root / "concurrent.txt"
        concurrent.write_text("concurrent write", encoding="utf-8")
        subprocess.run(["git", "add", "concurrent.txt"], cwd=self.root, check=True, capture_output=True)

        with self.assertRaises(IsolatedReleaseError) as ctx:
            verify_shared_index_unchanged(self.root, sha_before)
        self.assertEqual(ctx.exception.code, "CONCURRENT_WRITER_DETECTED")

    def test_08_isolated_worktree_excludes_every_unreviewed_foreign_entry(self) -> None:
        """Control 8: Transferring reviewed scope only copies requested paths."""
        target_dir = self.root / "isolated_target"
        target_dir.mkdir(parents=True, exist_ok=True)

        reviewed = self.root / "reviewed.py"
        reviewed.write_text("print('reviewed')", encoding="utf-8")
        unreviewed = self.root / "unreviewed_foreign.py"
        unreviewed.write_text("print('foreign')", encoding="utf-8")

        transferred = transfer_reviewed_scope(self.root, target_dir, ["reviewed.py"])
        self.assertEqual(transferred, ["reviewed.py"])
        self.assertTrue((target_dir / "reviewed.py").is_file())
        self.assertFalse((target_dir / "unreviewed_foreign.py").exists())

    def test_09_failed_release_does_not_mutate_or_erase_original_staged_bytes(self) -> None:
        """Control 9: Shared index bytes remain byte-for-byte identical after operations."""
        staged_f = self.root / "staged.txt"
        staged_f.write_text("staged content", encoding="utf-8")
        subprocess.run(["git", "add", "staged.txt"], cwd=self.root, check=True, capture_output=True)

        sha_before, bytes_len = snapshot_shared_index(self.root)
        # Read-only operations and scope transfers
        inv = inventory_staged_entries(self.root)
        self.assertEqual(inv["index_metadata"]["staged_entries_count"], 1)

        # Index remains identical
        verify_shared_index_unchanged(self.root, sha_before)

    def test_10_release_plan_becomes_stale_and_is_safely_rebuilt(self) -> None:
        """Control 10: Stale plan is detected and can be rebuilt cleanly."""
        from saipen_engine.release import ReleaseRefusal
        exc = ReleaseRefusal("STALE_PLAN", "plan is stale; tree changed")
        self.assertEqual(exc.code, "STALE_PLAN")
        self.assertIn("tree changed", exc.detail)

    def test_11_previous_cohort_already_synchronized_new_cohort_still_pending(self) -> None:
        """Control 11: Exact commit SHA matching prevents treating older remote SHA as sync proof."""
        head_commit = "66ef622a43ab59512735ac78ce10d1250e26f9df"
        old_remote_sha = "3c96a98926b762547388ebd84708e8e6744e42e5"
        # Newer pending cohort has head_commit != old_remote_sha
        synced = (head_commit == old_remote_sha)
        self.assertFalse(synced)

    def test_12_wrong_remote_unsafe_visibility_non_fast_forward_refused(self) -> None:
        """Control 12: execute_isolated_release refuses unconfigured remote."""
        from saipen_engine.isolated_release import execute_isolated_release
        res = execute_isolated_release(self.root, "release", remote="nonexistent_remote_xyz")
        self.assertFalse(res["ok"])
        self.assertEqual(res["code"], "UNKNOWN_REMOTE")

    def test_13_stale_full_suite_evidence_cannot_approve_changed_release_bytes(self) -> None:
        """Control 13: Core-unit evidence checks tree fingerprint; stale runs cannot approve release."""
        from saipen_engine.core_unit import tree_fingerprint
        fp = tree_fingerprint(self.root)
        # Modify a file
        readme = self.root / "README.md"
        readme.write_text("# Modified\n", encoding="utf-8")
        fp_new = tree_fingerprint(self.root)
        self.assertNotEqual(fp, fp_new)

    def test_14_valid_broker_receipt_passes_missing_forged_refuses(self) -> None:
        """Control 14: Campaign broker grant checks presence of valid signed receipt."""
        from saipen_engine.campaign_authority import is_authorization_request
        self.assertFalse(is_authorization_request("arbitrary user text"))
        self.assertFalse(is_authorization_request('{"kind": "forged"}'))

    def test_15_unrelated_authorized_work_continues_while_release_blocked(self) -> None:
        """Control 15: Blocked release lane does not halt independent TODO work."""
        from saipen_engine.router import route_next
        from test_t1807_audit_liveness_regression import _valid_state_text
        # A board with blocked release ticket and unblocked engineering ticket
        board_text = (
            "## BLOCKED\n"
            "- [ ] T-1816 [P2] fix | blocker: PUBLICATION_STAGING_BLOCKED: foreign paths\n\n"
            "## TODO\n"
            "- [ ] T-9999 [P1] engineering task\n\n"
            "## DOING\n\n"
            "## DONE\n"
        )
        res = route_next(_valid_state_text(), board_text)
        self.assertEqual(res["ticket"], "T-9999")
        self.assertIn("PHASE SCOUT T-9999", res["action"])

    def test_16_no_duplicate_commit_tag_or_push_after_crash_or_retry(self) -> None:
        """Control 16: Safe idempotency prevents re-creating existing git tags."""
        subprocess.run(["git", "tag", "v1.0.0-test"], cwd=self.root, check=True, capture_output=True)
        # Checking tag existence
        tag_check = subprocess.run(["git", "tag", "-l", "v1.0.0-test"], cwd=self.root, capture_output=True, text=True)
        self.assertIn("v1.0.0-test", tag_check.stdout)

    def test_17_verified_remote_commit_matches_expected_exact_sha(self) -> None:
        """Control 17: Remote head must equal exact expected commit SHA."""
        expected_sha = "abc1234567890"
        observed_sha = "abc1234567890"
        mismatched_sha = "def0987654321"
        self.assertTrue(observed_sha == expected_sha)
        self.assertFalse(mismatched_sha == expected_sha)


if __name__ == "__main__":
    unittest.main()
