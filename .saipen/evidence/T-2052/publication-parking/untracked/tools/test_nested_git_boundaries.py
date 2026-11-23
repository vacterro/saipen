"""A nested Git entity is classified by ownership, never by path shape.

Measured incident (BZDECOMP, 12.11.26): the consumer kept a linked worktree at
``contributions/.tooling/upstream-parser`` -- the work tree of its own clone at
``contributions/BZNTools-20261027``. Git never descends into an embedded
repository, so ``git ls-files --others`` reported the DIRECTORY with a trailing
slash:

    b'contributions/.tooling/upstream-parser/'

``_path_from_git`` split that on ``/``, met an empty component and refused the
whole listing as a "non-canonical path". ``compute_source_identity`` therefore
raised, the validator recorded an empty source identity, and every conformance
read of the project said ``STALE_FAIL`` with reason
``source-identity-unavailable`` -- a condition the validator explicitly refuses
to auto-cure. The agent was told to run ``saipen validate``, ran it, and got the
byte-identical failure: an unproductive loop with no exit.

The fix keeps the boundary exactly where it was and moves the DECISION to the
existing ownership contract, ``.saipen/source-nested-repos.json``:

* a declared repository is covered by ``_nested_binding`` (its own HEAD plus its
  own working-tree delta), so the outer delta skips the boundary entry;
* an undeclared one FAILS with the exact remedy named -- a nested repository is
  never silently included, excluded or modified;
* everything else Git calls a directory boundary (a reparse point, a directory
  that is not a work-tree root, a path that escapes the project) stays fatal.

Both directions are pinned: the legitimate worktree stops aborting the capture,
and the foreign one cannot become invisible.
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
    _declared_nested_repo_paths,
    _parse_git_delta,
    compute_source_identity,
)

CONFIG_REL = NESTED_REPOS_CONFIG_REL

#: The SHA a gitlink points at in the fixtures. Any object name works: Git only
#: compares the entry's recorded object, it never resolves it for a delta.
GITLINK_SHA = "1" * 40
GITLINK_SHA_OTHER = "2" * 40


def git(cwd: Path | str, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def git_text(cwd: Path | str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ).stdout.decode("utf-8", "replace")


class NestedGitBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        (self.root / "outer.txt").write_text("outer\n", encoding="utf-8")
        git(self.root, "add", "outer.txt")
        git(self.root, "commit", "-q", "-m", "outer")

    # --- fixture helpers ---------------------------------------------------

    def make_repo(self, rel: str, filename: str = "product.txt", body: str = "v1\n") -> Path:
        path = self.root / rel
        path.mkdir(parents=True)
        git(path, "init", "-q", "-b", "main")
        git(path, "config", "user.email", "t@example.invalid")
        git(path, "config", "user.name", "t")
        (path / filename).write_text(body, encoding="utf-8")
        git(path, "add", filename)
        git(path, "commit", "-q", "-m", "product v1")
        return path

    def make_worktree(self, repo: Path, rel: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        # Detached, exactly like the measured consumer worktree: a linked work
        # tree cannot check out the branch its main worktree already holds.
        git(repo, "worktree", "add", "-q", "--detach", str(path), "main")
        return path

    def declare(self, repos: list[str]) -> None:
        path = self.root / CONFIG_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"schema_version": 1, "nested_repos": repos}), encoding="utf-8"
        )

    def fingerprint(self) -> str:
        return compute_source_identity(self.root).source_tree_fingerprint

    def failure(self) -> str:
        with self.assertRaises(FreshnessError) as ctx:
            self.fingerprint()
        return str(ctx.exception)

    # --- 1. the control: nothing nested at all -----------------------------

    def test_plain_repository_still_vouchers_a_git_delta_identity(self) -> None:
        ident = compute_source_identity(self.root)
        self.assertTrue(ident.source_tree_fingerprint.startswith("git-delta-v1:"))
        self.assertEqual(ident.source_head, git_text(self.root, "rev-parse", "HEAD").strip())
        (self.root / "outer.txt").write_text("edited\n", encoding="utf-8")
        self.assertNotEqual(self.fingerprint(), ident.source_tree_fingerprint)

    # --- 2/14. a legitimate linked worktree --------------------------------

    def test_authorized_linked_worktree_no_longer_aborts_the_capture(self) -> None:
        """The incident itself: an untracked linked worktree is a boundary."""

        repo = self.make_repo("contributions/BZNTools-20261027")
        self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        # Git reports the boundary exactly this way -- this is the assertion the
        # whole defect hung on.
        listing = git_text(
            self.root, "ls-files", "-z", "--others", "--exclude-standard"
        )
        self.assertIn("contributions/.tooling/upstream-parser/", listing)

        self.declare(["contributions/BZNTools-20261027", "contributions/.tooling/upstream-parser"])
        ident = compute_source_identity(self.root)
        self.assertTrue(ident.source_tree_fingerprint.startswith("git-delta-v1:"))

    def test_authorized_worktree_content_is_bound_not_invisible(self) -> None:
        repo = self.make_repo("contributions/BZNTools-20261027")
        worktree = self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        self.declare(["contributions/BZNTools-20261027", "contributions/.tooling/upstream-parser"])
        before = self.fingerprint()
        (worktree / "product.txt").write_text("v2\n", encoding="utf-8")
        self.assertNotEqual(self.fingerprint(), before)

    def test_dirty_authorized_worktree_is_still_a_valid_capture(self) -> None:
        repo = self.make_repo("contributions/BZNTools-20261027")
        worktree = self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        (worktree / "product.txt").write_text("dirty\n", encoding="utf-8")
        (worktree / "untracked.txt").write_text("new\n", encoding="utf-8")
        self.declare(["contributions/BZNTools-20261027", "contributions/.tooling/upstream-parser"])
        self.assertTrue(self.fingerprint().startswith("git-delta-v1:"))

    # --- 3/5/11. every undeclared foreign entity stays protected -----------

    def test_undeclared_linked_worktree_fails_with_the_contract_named(self) -> None:
        repo = self.make_repo("contributions/BZNTools-20261027")
        self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        detail = self.failure()
        self.assertIn("contributions/.tooling/upstream-parser", detail)
        self.assertIn("no ownership contract", detail)
        self.assertIn(CONFIG_REL.as_posix(), detail)
        self.assertIn("nested_repos", detail)

    def test_undeclared_independent_repository_fails_with_the_contract_named(self) -> None:
        self.make_repo("vendor/foreign")
        detail = self.failure()
        self.assertIn("vendor/foreign", detail)
        self.assertIn("no ownership contract", detail)

    def test_the_undeclared_failure_is_deterministic(self) -> None:
        """An identical tree yields the identical refusal, so a retry is visible."""

        self.make_repo("vendor/foreign")
        self.assertEqual(self.failure(), self.failure())

    def test_declared_independent_repository_is_bound(self) -> None:
        nested = self.make_repo("vendor/owned")
        self.declare(["vendor/owned"])
        before = self.fingerprint()
        (nested / "product.txt").write_text("v2\n", encoding="utf-8")
        self.assertNotEqual(self.fingerprint(), before)

    # --- 4. submodules / gitlinks -----------------------------------------

    def test_declared_changed_gitlink_is_covered_by_the_binding(self) -> None:
        git(self.root, "update-index", "--add", "--cacheinfo", f"160000,{GITLINK_SHA},vendor/sub")
        git(self.root, "commit", "-q", "-m", "add gitlink")
        # A pointer move is exactly what the outer delta reports.
        git(self.root, "update-index", "--cacheinfo", f"160000,{GITLINK_SHA_OTHER},vendor/sub")
        (self.root / "vendor" / "sub").mkdir(parents=True, exist_ok=True)
        git(self.root / "vendor" / "sub", "init", "-q", "-b", "main")
        git(self.root / "vendor" / "sub", "config", "user.email", "t@example.invalid")
        git(self.root / "vendor" / "sub", "config", "user.name", "t")
        (self.root / "vendor" / "sub" / "x.txt").write_text("x\n", encoding="utf-8")
        git(self.root / "vendor" / "sub", "add", "x.txt")
        git(self.root / "vendor" / "sub", "commit", "-q", "-m", "x")
        self.declare(["vendor/sub"])
        self.assertTrue(self.fingerprint().startswith("git-delta-v1:"))

    def test_undeclared_changed_gitlink_stays_fatal(self) -> None:
        """Fed the raw record directly: Git only emits this shape for a real
        submodule, and the fixture must not depend on one being checkable out."""

        (self.root / "vendor" / "sub").mkdir(parents=True)
        record = (
            b":160000 160000 " + GITLINK_SHA[:7].encode() + b" "
            + GITLINK_SHA_OTHER[:7].encode() + b" M\0vendor/sub\0"
        )
        with self.assertRaises(FreshnessError) as ctx:
            _parse_git_delta(self.root, record, b"")
        detail = str(ctx.exception)
        self.assertIn("submodule", detail)
        self.assertIn("nested_repos", detail)

    def test_declared_gitlink_record_is_skipped_not_fatal(self) -> None:
        nested = self.root / "vendor" / "sub"
        nested.mkdir(parents=True)
        git(nested, "init", "-q", "-b", "main")
        git(nested, "config", "user.email", "t@example.invalid")
        git(nested, "config", "user.name", "t")
        (nested / "x.txt").write_text("x\n", encoding="utf-8")
        git(nested, "add", "x.txt")
        git(nested, "commit", "-q", "-m", "x")
        self.declare(["vendor/sub"])
        record = (
            b":160000 160000 " + GITLINK_SHA[:7].encode() + b" "
            + GITLINK_SHA_OTHER[:7].encode() + b" M\0vendor/sub\0"
        )
        self.assertEqual(_parse_git_delta(self.root, record, b""), [])

    # --- 6. broken Git metadata -------------------------------------------

    def test_broken_git_control_file_hashes_local_bytes_only(self) -> None:
        """A dangling ``.git`` file is not a repository boundary.

        Git descends past it and reports the ordinary files inside, so the honest
        classification is "untracked local source": nothing is read outside the
        project and nothing is skipped. Measured, not assumed.
        """

        broken = self.root / "broken"
        broken.mkdir()
        (broken / ".git").write_text("gitdir: /nonexistent/elsewhere\n", encoding="utf-8")
        (broken / "x.txt").write_text("x\n", encoding="utf-8")
        first = self.fingerprint()
        (broken / "x.txt").write_text("y\n", encoding="utf-8")
        self.assertNotEqual(self.fingerprint(), first)

    # --- 7/8. declared but unusable ---------------------------------------

    def test_declared_worktree_that_disappeared_fails_closed(self) -> None:
        self.declare(["contributions/upstream-parser"])
        detail = self.failure()
        self.assertIn("missing", detail)

    def test_declared_path_outside_the_project_fails_closed(self) -> None:
        self.declare(["../elsewhere"])
        self.assertIn("escapes the project root", self.failure())

    # --- 9. reparse-point escape ------------------------------------------

    @unittest.skipUnless(os.name == "nt", "junction semantics are Windows-only")
    def test_declared_junction_is_refused(self) -> None:
        outside = self.root.parent / f"{self.root.name}-outside"
        outside.mkdir()
        self.addCleanup(lambda: subprocess.run(["cmd", "/c", "rmdir", str(outside)], check=False))
        link = self.root / "linked"
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if created.returncode != 0:
            self.skipTest("junction could not be created in this environment")
        self.declare(["linked"])
        detail = self.failure()
        self.assertIn("reparse point", detail)
        self.assertIn("linked", detail)

    # --- 12. the listing shape itself -------------------------------------

    def test_directory_boundary_that_is_not_a_repository_is_refused(self) -> None:
        """A synthetic ``dir/`` entry with no repository behind it must fail.

        Git only emits this shape for an embedded repository, so the fixture
        feeds the parser directly: a boundary that is neither a declared
        repository nor a work-tree root can never become a fabricated file.
        """

        (self.root / "plain").mkdir()
        (self.root / "plain" / "f.txt").write_text("f\n", encoding="utf-8")
        with self.assertRaises(FreshnessError) as ctx:
            _parse_git_delta(self.root, b"", b"plain/")
        self.assertIn("not a repository", str(ctx.exception))

    def test_boundary_escape_is_refused_before_any_read(self) -> None:
        with self.assertRaises(FreshnessError) as ctx:
            _parse_git_delta(self.root, b"", b"../outside/")
        self.assertIn("non-canonical", str(ctx.exception))

    # --- 13. repeated capture mutates nothing -----------------------------

    def test_repeated_capture_is_stable_and_leaves_git_metadata_alone(self) -> None:
        repo = self.make_repo("contributions/BZNTools-20261027")
        worktree = self.make_worktree(repo, "contributions/.tooling/upstream-parser")
        self.declare(["contributions/BZNTools-20261027", "contributions/.tooling/upstream-parser"])
        admin = repo / ".git" / "worktrees" / "upstream-parser"
        before_admin = sorted(p.name for p in admin.iterdir())
        before_status = git_text(self.root, "status", "--porcelain")
        before_worktree_status = git_text(worktree, "status", "--porcelain")
        first = compute_source_identity(self.root)
        second = compute_source_identity(self.root)
        self.assertEqual(first.source_tree_fingerprint, second.source_tree_fingerprint)
        self.assertEqual(first.source_head, second.source_head)
        self.assertEqual(sorted(p.name for p in admin.iterdir()), before_admin)
        self.assertEqual(git_text(self.root, "status", "--porcelain"), before_status)
        self.assertEqual(git_text(worktree, "status", "--porcelain"), before_worktree_status)

    # --- Windows path normalisation ---------------------------------------

    @unittest.skipUnless(os.name == "nt", "case-insensitive paths are Windows-only")
    def test_case_differing_declaration_owns_the_same_directory(self) -> None:
        self.make_repo("Contributions/Tools")
        self.declare(["contributions/tools"])
        self.assertIn(_nested_key_of("contributions/tools"), _declared_nested_repo_paths(self.root))
        self.assertTrue(self.fingerprint().startswith("git-delta-v1:"))


def _nested_key_of(rel: str) -> bytes:
    from freshness import _nested_key

    return _nested_key(rel.encode("utf-8"))


# ---------------------------------------------------------------------------
# The loop, not only the crash: an uncomputable source identity is NOT a
# condition `saipen validate` can clear, so the decision must stop advertising
# the identical retry and carry a stable fingerprint of the blockage instead.

try:  # the shared conformance fixture lives with the T-1412 truth controls
    from test_t1412_conformance_truth import T1412Base, write_receipt  # noqa: E402
    from saipen_engine import conformance as C  # noqa: E402

    _HAVE_FIXTURE = True
except Exception:  # pragma: no cover -- fixture absent in a stripped checkout
    _HAVE_FIXTURE = False


@unittest.skipUnless(_HAVE_FIXTURE, "conformance fixture unavailable")
class RetryBoundary(unittest.TestCase):
    """An unchanged, unrecoverable blockage is recognisable and not retried."""

    def setUp(self) -> None:
        self._fixture = T1412Base(methodName="runTest")
        self._fixture.setUp()
        self.addCleanup(self._fixture.doCleanups)

    def blocked_project(self) -> Path:
        root = self._fixture.make_project("blocked")
        self._fixture.assert_fast_gate_clean(root)
        # A receipt that WAS valid evidence for this tree.
        write_receipt(root, "FAIL")
        # Then the identity becomes uncomputable, exactly like the incident: an
        # untracked embedded repository with no ownership contract.
        nested = root / "vendor" / "foreign"
        nested.mkdir(parents=True)
        git(nested, "init", "-q", "-b", "main")
        git(nested, "config", "user.email", "t@example.invalid")
        git(nested, "config", "user.name", "t")
        (nested / "x.txt").write_text("x\n", encoding="utf-8")
        git(nested, "add", "x.txt")
        git(nested, "commit", "-q", "-m", "x")
        return root

    def test_unavailable_identity_blocks_the_identical_retry(self) -> None:
        root = self.blocked_project()
        status = C.conformance_status(root, gate="core")
        self.assertEqual(status["status"], C.STATUS_STALE_FAIL)
        self.assertEqual(status["stale_reason"], C.STALE_REASON_SOURCE_IDENTITY_UNAVAILABLE)
        self.assertTrue(status["retry_blocked"])
        self.assertEqual(len(status["retry_fingerprint"]), 16)
        # The same tree, measured twice, names the same blockage.
        again = C.conformance_status(root, gate="core")
        self.assertEqual(again["retry_fingerprint"], status["retry_fingerprint"])

    def test_decision_names_the_input_not_the_retry(self) -> None:
        root = self.blocked_project()
        decision = C.conformance_decision(root, gate="core")
        self.assertFalse(decision["healthy"])
        self.assertTrue(decision["retry_blocked"])
        self.assertEqual(decision["repair_status"], "INPUT_REQUIRED")
        self.assertEqual(decision["diagnostic"]["kind"], "INPUT_REQUIRED")
        self.assertIn("cannot change this condition", decision["diagnostic"]["note"])
        # The command stays advertised -- it is the one run that re-reads the
        # evidence once the input is repaired -- but it is no longer presented
        # as the cure.
        self.assertEqual(decision["remediation_command"], C.CONFORMANCE_REMEDIATION_COMMAND)

    def test_a_different_blockage_gets_a_different_fingerprint(self) -> None:
        base = C.blocking_fingerprint(
            {"blocking_findings": {"problems": [{"finding_key": "a", "detail_hash": "1"}]}},
            C.STALE_REASON_SOURCE_IDENTITY_UNAVAILABLE,
        )
        other = C.blocking_fingerprint(
            {"blocking_findings": {"problems": [{"finding_key": "b", "detail_hash": "2"}]}},
            C.STALE_REASON_SOURCE_IDENTITY_UNAVAILABLE,
        )
        self.assertNotEqual(base, other)
        self.assertEqual(
            base,
            C.blocking_fingerprint(
                {"blocking_findings": {"problems": [{"detail_hash": "1", "finding_key": "a"}]}},
                C.STALE_REASON_SOURCE_IDENTITY_UNAVAILABLE,
            ),
        )

    def test_recoverable_staleness_is_not_marked_retry_blocked(self) -> None:
        root = self._fixture.make_project("recoverable")
        write_receipt(root, "FAIL", source_head="0" * 40, source_fp="git-delta-v1:" + "0" * 64)
        status = C.conformance_status(root, gate="core")
        self.assertFalse(status.get("retry_blocked"))
        self.assertIsNone(status.get("retry_fingerprint"))
        self.assertTrue(C.stale_recoverable(status))


if __name__ == "__main__":
    unittest.main()
