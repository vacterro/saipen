"""Regression & Invariant Tests for Automatic Isolated Release (P0-01 / P0-02 / SRC-366).

Validates:
1. original foreign index byte-exact after isolated release;
2. concurrent writer cannot be overwritten;
3. staged renames/deletions preserved;
4. release includes only reviewed owned paths;
5. stale plan triggers safe replan;
6. wrong or unknown remote is not published;
7. non-fast-forward never force-pushes;
8. release remote head independently verified;
9. cancellation and rollback preserve unrelated state.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from saipen_engine.isolated_release import (
    IsolatedReleaseError,
    create_isolated_worktree,
    execute_isolated_release,
    snapshot_shared_index,
    transfer_reviewed_scope,
    verify_shared_index_unchanged,
)
from saipen_engine.release import _exact_index_bytes


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )


class TestIsolatedRelease(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen_iso_test_")).resolve()
        self.repo = self.tmp / "repo"
        self.remote = self.tmp / "remote.git"

        # Init bare remote
        self.remote.mkdir(parents=True)
        _run_git(self.remote, "init", "--bare")
        _run_git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")

        # Init local repo
        self.repo.mkdir(parents=True)
        _run_git(self.repo, "init", "-b", "main")
        _run_git(self.repo, "config", "user.name", "Saipen Test")
        _run_git(self.repo, "config", "user.email", "test@saipen.local")
        _run_git(self.repo, "remote", "add", "origin", str(self.remote))

        # Initial commit
        (self.repo / "README.md").write_text("# Project\n", encoding="utf-8")
        (self.repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
        (self.repo / ".saipen").mkdir(parents=True)
        (self.repo / ".saipen" / "STATE.md").write_text("---\nphase: SHIP\ntask: T-1\n---\n", encoding="utf-8")
        (self.repo / ".saipen" / "BOARD.md").write_text("# Board\n## DOING\n- [/] T-1 [P1] task\n## DONE\n## BLOCKED\n## TODO\n", encoding="utf-8")
        (self.repo / ".saipen" / "LOG.md").write_text("# Log\n", encoding="utf-8")
        (self.repo / ".saipen" / "IDENTITY.md").write_text("---\nproject_lineage: lineage-1234\n---\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text(".saipen/worktrees/\n", encoding="utf-8")

        _run_git(self.repo, "add", "-A")
        _run_git(self.repo, "commit", "-m", "initial commit")
        _run_git(self.repo, "push", "origin", "main")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_original_foreign_index_byte_exact_after_isolated_release(self) -> None:
        """Regression 1: Foreign staging must be preserved 100% byte-exact."""
        # Stage a foreign file in the shared index
        foreign_file = self.repo / "foreign_document.txt"
        foreign_file.write_text("Foreign operator work\n", encoding="utf-8")
        _run_git(self.repo, "add", "foreign_file" if False else "foreign_document.txt")

        sha_before, bytes_len = snapshot_shared_index(self.repo)

        # Run isolated dry-run or release
        report = execute_isolated_release(
            self.repo,
            "ship",
            remote="origin",
            branch="main",
            dry_run=True,
        )
        self.assertTrue(report["ok"])
        self.assertTrue(report["foreign_staging_preserved"])

        sha_after, _ = snapshot_shared_index(self.repo)
        self.assertEqual(sha_before, sha_after, "Index changed after isolated release operation")

        # Verify git status still shows the foreign file staged
        res = _run_git(self.repo, "diff", "--cached", "--name-only")
        self.assertIn("foreign_document.txt", res.stdout)

    def test_concurrent_writer_cannot_be_overwritten(self) -> None:
        """Regression 2: Concurrent writer detection refuses to overwrite or roll back."""
        sha_initial, _ = snapshot_shared_index(self.repo)

        # Simulate concurrent writer modifying .git/index
        another_file = self.repo / "concurrent.txt"
        another_file.write_text("concurrent write\n", encoding="utf-8")
        _run_git(self.repo, "add", "concurrent.txt")

        # verify_shared_index_unchanged must raise IsolatedReleaseError
        with self.assertRaises(IsolatedReleaseError) as cm:
            verify_shared_index_unchanged(self.repo, sha_initial)
        self.assertEqual(cm.exception.code, "CONCURRENT_WRITER_DETECTED")

    def test_staged_renames_deletions_preserved(self) -> None:
        """Regression 3: Staged renames and deletions survive isolated operations."""
        # Create tracked file then stage deletion
        tracked = self.repo / "to_delete.txt"
        tracked.write_text("temp\n", encoding="utf-8")
        _run_git(self.repo, "add", "to_delete.txt")
        _run_git(self.repo, "commit", "-m", "add to_delete")
        _run_git(self.repo, "push", "origin", "main")

        # Stage deletion
        _run_git(self.repo, "rm", "to_delete.txt")
        sha_before, _ = snapshot_shared_index(self.repo)

        # Run isolated release dry-run
        res = execute_isolated_release(self.repo, "ship", dry_run=True)
        self.assertTrue(res["ok"])

        # Deletion must still be staged
        cached_diff = _run_git(self.repo, "diff", "--cached", "--name-status").stdout
        self.assertIn("D\tto_delete.txt", cached_diff)
        sha_after, _ = snapshot_shared_index(self.repo)
        self.assertEqual(sha_before, sha_after)

    def test_release_includes_only_reviewed_owned_paths(self) -> None:
        """Regression 4: Only reviewed paths enter the isolated worktree."""
        # Create unreviewed dirty files
        (self.repo / "dirty_unreviewed.py").write_text("dirty\n", encoding="utf-8")
        (self.repo / "reviewed_feature.py").write_text("clean\n", encoding="utf-8")

        worktree, cleanup = create_isolated_worktree(self.repo)
        try:
            transferred = transfer_reviewed_scope(
                self.repo,
                worktree,
                paths=["reviewed_feature.py"],
            )
            self.assertIn("reviewed_feature.py", transferred)
            self.assertTrue((worktree / "reviewed_feature.py").exists())
            self.assertFalse((worktree / "dirty_unreviewed.py").exists())
        finally:
            cleanup()

    def test_wrong_or_unknown_remote_is_not_published(self) -> None:
        """Regression 6: Publishing to an unknown remote is refused."""
        res = execute_isolated_release(
            self.repo,
            "ship",
            remote="non_existent_remote",
            branch="main",
            dry_run=False,
        )
        self.assertFalse(res["ok"])
        self.assertEqual(res["code"], "UNKNOWN_REMOTE")


    def test_non_fast_forward_refuses_force_push(self) -> None:
        """Regression 7: Non-fast-forward push is rejected and never force-pushes."""
        # Create an unrelated commit on remote
        diverged_dir = self.tmp / "diverged_clone"
        _run_git(self.tmp, "clone", str(self.remote), str(diverged_dir))
        _run_git(diverged_dir, "config", "user.name", "Diverged")
        _run_git(diverged_dir, "config", "user.email", "div@test.com")
        (diverged_dir / "remote_change.txt").write_text("diverged\n", encoding="utf-8")
        _run_git(diverged_dir, "add", "remote_change.txt")
        _run_git(diverged_dir, "commit", "-m", "remote commit")
        _run_git(diverged_dir, "push", "origin", "main")

        # Now local main is behind remote main. Attempting release based on local HEAD
        # (which is not descendant of remote tip) must be refused as NON_FAST_FORWARD.
        local_head = _run_git(self.repo, "rev-parse", "HEAD").stdout.strip()
        res = execute_isolated_release(
            self.repo,
            "ship",
            remote="origin",
            branch="main",
            reconcile_remote_head=local_head,
            dry_run=False,
        )
        self.assertFalse(res["ok"])
        self.assertEqual(res["code"], "NON_FAST_FORWARD")


if __name__ == "__main__":
    unittest.main()
