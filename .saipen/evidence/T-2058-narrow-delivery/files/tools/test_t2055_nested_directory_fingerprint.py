"""A valid Git directory/nested-repository record carries content, not silence.

Measured incident (BZDECOMP, 13.11.26). Git never descends into an embedded
repository, so ``git ls-files --others`` reports the DIRECTORY with a trailing
slash:

    b'contributions/.tooling/upstream-parser/'

``_path_from_git`` split that on ``/``, met an empty final component and refused
the whole listing as a "non-canonical path". ``compute_source_identity``
raised, the validator recorded an empty source identity, and every
``saipen validate`` said ``STALE_FAIL`` / ``source-identity-unavailable`` --
a condition the validator explicitly refuses to auto-cure, so the operator was
told to run the command that reports the same failure again.

The contract pinned here:

* a directory boundary that is a Git work-tree root is FINGERPRINTED -- its own
  HEAD, its own delta and the bytes of its untracked files -- with no
  declaration file required. The record participates in the outer identity, so
  a change inside the nested repository moves the outer fingerprint;
* the fingerprint is deterministic and root-independent: two identical trees in
  two different temporary directories yield the same identity;
* the user's repository is never deleted, moved, ignored or staged to get a
  green receipt;
* dangerous input stays fatal: absolute paths, traversal, NUL, reparse
  points/junctions, and a ``dir/`` record that is not a repository at all.

The declaration contract ``.saipen/source-nested-repos.json`` keeps its meaning
for projects that already use it; it is no longer a precondition.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from freshness import (  # noqa: E402
    NESTED_REPOS_CONFIG_REL,
    FreshnessError,
    _nested_boundary_from_git,
    _parse_git_delta,
    compute_source_identity,
)


#: Two fixed commit instants. They exist so the determinism test can PROVE
#: that its two fixtures hold different commit ids -- the property that made a
#: HEAD-based nested identity flaky -- while their content is identical.
DATE_EARLY = "2020-01-01T00:00:00Z"
DATE_LATE = "2021-02-02T00:00:00Z"


def git(cwd: Path | str, *args: str, when: str | None = None) -> None:
    env = None
    if when is not None:
        env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )


def git_text(cwd: Path | str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ).stdout.decode("utf-8", "replace")


class Fixture(unittest.TestCase):
    """An outer repository whose only interesting content is a nested one."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)

    def make_outer(self, name: str = "outer", *, when: str | None = None) -> Path:
        root = self.base / name
        root.mkdir()
        git(root, "init", "-q", "-b", "main")
        git(root, "config", "user.email", "t@example.invalid")
        git(root, "config", "user.name", "t")
        (root / "outer.txt").write_text("outer\n", encoding="utf-8")
        git(root, "add", "outer.txt")
        git(root, "commit", "-q", "-m", "outer", when=when)
        return root

    def make_repo(
        self, parent: Path, rel: str, body: str = "v1\n", *, when: str | None = None
    ) -> Path:
        path = parent / rel
        path.mkdir(parents=True)
        git(path, "init", "-q", "-b", "main")
        git(path, "config", "user.email", "t@example.invalid")
        git(path, "config", "user.name", "t")
        (path / "product.txt").write_text(body, encoding="utf-8")
        git(path, "add", "product.txt")
        git(path, "commit", "-q", "-m", "product v1", when=when)
        return path

    def make_worktree(self, repo: Path, rel: str) -> Path:
        path = repo.parent.parent / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        git(repo, "worktree", "add", "-q", "--detach", str(path), "main")
        return path

    def fingerprint(self, root: Path) -> str:
        return compute_source_identity(root).source_tree_fingerprint


class NestedDirectoryIsFingerprinted(Fixture):
    def test_untracked_linked_worktree_needs_no_declaration(self) -> None:
        """The incident itself: an undeclared linked worktree is a boundary."""

        root = self.make_outer()
        repo = self.make_repo(root, "contributions/BZNTools-20261027")
        self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        # Git reports the boundary exactly this way -- the whole defect hung on
        # this shape, so the fixture proves it instead of assuming it.
        listing = git_text(root, "ls-files", "-z", "--others", "--exclude-standard")
        self.assertIn("contributions/.tooling/upstream-parser/", listing)
        self.assertFalse((root / NESTED_REPOS_CONFIG_REL).exists())

        ident = compute_source_identity(root)
        self.assertTrue(ident.source_tree_fingerprint.startswith("git-delta-v1:"))
        self.assertEqual(
            ident.source_head, git_text(root, "rev-parse", "HEAD").strip()
        )

    def test_untracked_independent_repository_needs_no_declaration(self) -> None:
        root = self.make_outer()
        self.make_repo(root, "vendor/foreign")
        self.assertTrue(self.fingerprint(root).startswith("git-delta-v1:"))

    def test_repeated_capture_is_byte_identical(self) -> None:
        root = self.make_outer()
        repo = self.make_repo(root, "contributions/BZNTools-20261027")
        self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        self.assertEqual(self.fingerprint(root), self.fingerprint(root))

    def test_identical_trees_in_different_roots_share_one_fingerprint(self) -> None:
        """Determinism: no absolute path and no commit id may enter the record.

        The two fixtures are committed at two fixed instants, so their commit
        ids differ while their trees are identical. The identity must still be
        the same -- otherwise the same source would fingerprint differently
        depending on when it was checked out.
        """

        prints = []
        heads = []
        for name, when in (("first", DATE_EARLY), ("second", DATE_LATE)):
            root = self.make_outer(name, when=when)
            repo = self.make_repo(root, "contributions/BZNTools-20261027", when=when)
            self.make_worktree(repo, "contributions/.tooling/upstream-parser")
            heads.append(git_text(repo, "rev-parse", "HEAD").strip())
            prints.append(self.fingerprint(root))
        self.assertNotEqual(heads[0], heads[1], "fixture must hold two commit ids")
        self.assertEqual(prints[0], prints[1])

    def test_nested_tracked_content_moves_the_outer_fingerprint(self) -> None:
        root = self.make_outer()
        repo = self.make_repo(root, "contributions/BZNTools-20261027")
        worktree = self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        before = self.fingerprint(root)
        (worktree / "product.txt").write_text("v2\n", encoding="utf-8")
        self.assertNotEqual(self.fingerprint(root), before)

    def test_nested_untracked_content_moves_the_outer_fingerprint(self) -> None:
        """An untracked file's BYTES count, not only its name in the listing."""

        root = self.make_outer()
        repo = self.make_repo(root, "contributions/BZNTools-20261027")
        worktree = self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        scratch = worktree / "notes.txt"
        scratch.write_text("draft one\n", encoding="utf-8")
        before = self.fingerprint(root)
        # Same path, same size, same mtime: only the bytes differ.
        stamp = scratch.stat()
        scratch.write_text("draft two\n", encoding="utf-8")
        os.utime(scratch, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertNotEqual(self.fingerprint(root), before)

    def test_nested_commit_moves_the_outer_fingerprint(self) -> None:
        root = self.make_outer()
        repo = self.make_repo(root, "contributions/BZNTools-20261027")
        self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        before = self.fingerprint(root)
        (repo / "product.txt").write_text("v2\n", encoding="utf-8")
        git(repo, "commit", "-q", "-am", "product v2")
        self.assertNotEqual(self.fingerprint(root), before)

    def test_unborn_nested_repository_is_still_fingerprinted(self) -> None:
        """A work tree with no commit yet must not abort the capture."""

        root = self.make_outer()
        nested = root / "vendor" / "fresh"
        nested.mkdir(parents=True)
        git(nested, "init", "-q", "-b", "main")
        (nested / "wip.txt").write_text("wip\n", encoding="utf-8")
        before = self.fingerprint(root)
        self.assertTrue(before.startswith("git-delta-v1:"))
        (nested / "wip.txt").write_text("wip two\n", encoding="utf-8")
        self.assertNotEqual(self.fingerprint(root), before)

    def test_the_user_repository_is_not_modified_by_the_capture(self) -> None:
        root = self.make_outer()
        repo = self.make_repo(root, "contributions/BZNTools-20261027")
        worktree = self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        admin = repo / ".git" / "worktrees" / "upstream-parser"
        before = (
            sorted(p.name for p in admin.iterdir()),
            git_text(root, "status", "--porcelain"),
            git_text(worktree, "status", "--porcelain"),
            sorted(p.name for p in worktree.iterdir()),
        )
        compute_source_identity(root)
        self.assertEqual(
            before,
            (
                sorted(p.name for p in admin.iterdir()),
                git_text(root, "status", "--porcelain"),
                git_text(worktree, "status", "--porcelain"),
                sorted(p.name for p in worktree.iterdir()),
            ),
        )
        self.assertTrue((worktree / "product.txt").is_file())


class DeclaredRepositoriesKeepTheirContract(Fixture):
    def test_declared_repository_is_still_bound(self) -> None:
        root = self.make_outer()
        nested = self.make_repo(root, "vendor/owned")
        config = root / NESTED_REPOS_CONFIG_REL
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            json.dumps({"schema_version": 1, "nested_repos": ["vendor/owned"]}),
            encoding="utf-8",
        )
        before = self.fingerprint(root)
        (nested / "product.txt").write_text("v2\n", encoding="utf-8")
        self.assertNotEqual(self.fingerprint(root), before)

    def test_declared_missing_repository_still_fails_closed(self) -> None:
        root = self.make_outer()
        config = root / NESTED_REPOS_CONFIG_REL
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            json.dumps({"schema_version": 1, "nested_repos": ["vendor/gone"]}),
            encoding="utf-8",
        )
        with self.assertRaises(FreshnessError) as ctx:
            compute_source_identity(root)
        self.assertIn("missing", str(ctx.exception))


class DangerousInputsStayBlocked(Fixture):
    def test_traversal_is_refused(self) -> None:
        root = self.make_outer()
        with self.assertRaises(FreshnessError) as ctx:
            _parse_git_delta(root, b"", b"../outside/")
        self.assertIn("non-canonical", str(ctx.exception))

    def test_absolute_path_is_refused(self) -> None:
        root = self.make_outer()
        with self.assertRaises(FreshnessError) as ctx:
            _parse_git_delta(root, b"", b"/etc/")
        self.assertIn("invalid directory boundary", str(ctx.exception))

    def test_nul_is_refused(self) -> None:
        """A NUL cannot cross a ``-z`` listing, so the classifier is fed directly."""

        root = self.make_outer()
        with self.assertRaises(FreshnessError) as ctx:
            _nested_boundary_from_git(root, b"vendor\x00evil/", frozenset())
        self.assertIn("invalid", str(ctx.exception))

    def test_directory_record_that_is_not_a_repository_is_refused(self) -> None:
        root = self.make_outer()
        (root / "plain").mkdir()
        (root / "plain" / "f.txt").write_text("f\n", encoding="utf-8")
        with self.assertRaises(FreshnessError) as ctx:
            _parse_git_delta(root, b"", b"plain/")
        self.assertIn("not a repository", str(ctx.exception))

    @unittest.skipUnless(os.name == "nt", "junction semantics are Windows-only")
    def test_junction_boundary_is_refused(self) -> None:
        root = self.make_outer()
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "x.txt").write_text("x\n", encoding="utf-8")
        link = root / "linked"
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if created.returncode != 0:
            self.skipTest("junction could not be created in this environment")
        with self.assertRaises(FreshnessError) as ctx:
            _parse_git_delta(root, b"", b"linked/")
        self.assertIn("reparse point", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
