"""The source-identity Git listing asks Git for the `.saipen` boundary (T-1900).

The source identity excludes `.saipen` — `_is_saipen_path` skips those paths in
`_parse_git_delta` and `_filtered_git_listing` projects them out before any
comparison. Leaving that exclusion to Python meant Git generated, and this
process decoded, the whole `.saipen` population on every pass: measured on the
live tree, 42 578 untracked paths emitted to keep 57, across three listings per
`compute_source_identity`.

The rule pinned here is that the exclusion is performed by Git as well, and that
it draws EXACTLY the same line as `_is_saipen_path` — no more and no less. Three
things could silently go wrong, so each has its own case:

1. The pathspec could change Git's SELECTION. Git selects relative to the
   caller's directory, so a project living in a subdirectory of a larger
   repository has never fingerprinted the rest of that repository. An
   exclusion-only pathspec preserves that exactly. Using `:/` (repository top
   level) instead would WIDEN the selection — it pulls in `../../outside-new.txt`
   for such a project and would change the identity of every subdirectory
   project. Run from the repository root, the two spellings coincide, which is
   why the subdirectory case has its own test.

2. The pathspec could be too NARROW, or the prefix rule could differ from
   `_is_saipen_path`. `.saipenicious.py`, `.saipen-src/` and `.saipenx/` are
   ordinary source and must survive; only the `.saipen` directory itself is the
   runtime boundary.

3. The surviving listing could change. The fingerprint is built from the
   filtered listing, so this test asserts the filtered view is IDENTICAL whether
   or not Git applies its own exclusion — the whole point is that this is a cost
   change, never a semantic one.

A recent Git that ignores the pathspec can only cost time: `_parse_git_delta`
and `_filtered_git_listing` keep their own predicate. The equivalence case
proves that too, because it compares against a listing produced WITHOUT any
pathspec.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from freshness import (  # noqa: E402
    _filtered_git_listing,
    _git_delta_listing,
    compute_source_identity,
)


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr[:400]!r}")
    return result.stdout


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(
        root,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@e",
        "commit",
        "--allow-empty",
        "-qm",
        "base",
    )


def _untracked(listing: tuple[bytes, bytes]) -> list[str]:
    return sorted(x.decode("utf-8") for x in listing[1].split(b"\0") if x)


class TestGitListingAsksForItsBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1900-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_the_exclusion_draws_exactly_the_saipen_boundary(self) -> None:
        """AC-01: `.saipen/` is excluded; lookalike names are ordinary source."""
        repo = self.tmp / "repo"
        _init_repo(repo)
        for relative in (
            ".saipen/STATE.md",
            ".saipen/deep/nested/BOARD.md",
            ".saipenicious.py",
            ".saipen-src/keep.py",
            ".saipenx/y.py",
            "plain.txt",
        ):
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x", encoding="utf-8")

        self.assertEqual(
            _untracked(_git_delta_listing(repo)),
            [".saipen-src/keep.py", ".saipenicious.py", ".saipenx/y.py", "plain.txt"],
        )

    def test_surviving_listing_is_identical_to_an_unpathspeced_listing(self) -> None:
        """AC-02: the exclusion is a cost change, never a semantic one.

        The control runs the pre-T-1900 Git invocations verbatim — no pathspec —
        and then applies `_filtered_git_listing`, which is what every consumer
        of the listing already compares. Both must agree byte for byte.
        """
        repo = self.tmp / "repo"
        _init_repo(repo)
        (repo / "tracked.txt").write_text("before\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "base")
        (repo / "tracked.txt").write_text("after\n", encoding="utf-8")
        for relative in ("untracked.py", ".saipen/STATE.md", ".saipen/logs/2.md"):
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x", encoding="utf-8")

        control_raw = _git(
            repo,
            "diff",
            "--raw",
            "-z",
            "--no-renames",
            "--no-ext-diff",
            "--ignore-submodules=none",
            "HEAD",
            "--",
        )
        control_untracked = _git(
            repo, "ls-files", "-z", "--others", "--exclude-standard", "--"
        )
        control = _filtered_git_listing((control_raw, control_untracked))
        subject = _filtered_git_listing(_git_delta_listing(repo))

        self.assertEqual(control, subject)
        self.assertEqual(sorted(control[1]), [b"untracked.py"])
        self.assertEqual(len(control[0]), 2, "the tracked modification stays fingerprinted")

    def test_the_exclusion_neither_narrows_nor_widens_scope(self) -> None:
        """AC-03: exclusion-only keeps Git's default selection, exactly.

        Git selects relative to the CALLER's directory: from a project that
        lives in a subdirectory of a larger repository, the listing has never
        covered the rest of that repository (`compute_source_identity` resolves
        its own root and Git scopes to it). The pathspec must preserve that as
        it stands, in both directions:

        - adding a positive pathspec beside the exclusion cannot narrow it
          further, since the default selection is already the caller's subtree;
        - using `:/` instead of relying on the default WIDENS it to the
          repository top level, which would fingerprint `../../outside-new.txt`
          and change the identity of every subdirectory project.

        So the subject is compared against a no-pathspec listing taken from the
        SAME directory, and the out-of-project path is asserted absent.
        """
        repo = self.tmp / "repo"
        _init_repo(repo)
        project = repo / "nested" / "project"
        (project / ".saipen").mkdir(parents=True)
        (project / "code.py").write_text("x", encoding="utf-8")
        (project / ".saipen" / "LOG.md").write_text("l", encoding="utf-8")
        (repo / "outside.txt").write_text("o", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "base")

        (project / "new.py").write_text("n", encoding="utf-8")
        (project / ".saipen" / "BOARD.md").write_text("b", encoding="utf-8")
        (repo / "outside-new.txt").write_text("z", encoding="utf-8")

        # Control: the pre-T-1900 invocations, run from the project directory.
        control_raw = _git(
            project,
            "diff",
            "--raw",
            "-z",
            "--no-renames",
            "--no-ext-diff",
            "--ignore-submodules=none",
            "HEAD",
            "--",
        )
        control_untracked = _git(
            project, "ls-files", "-z", "--others", "--exclude-standard", "--"
        )
        control = _filtered_git_listing((control_raw, control_untracked))
        subject = _filtered_git_listing(_git_delta_listing(project))

        self.assertEqual(control, subject)
        self.assertEqual(sorted(subject[1]), [b"new.py"])
        self.assertNotIn(
            b"../../outside-new.txt",
            subject[1],
            "the exclusion must not widen the selection to the repository top level",
        )
        self.assertNotIn(b"nested/project/.saipen/BOARD.md", subject[1])

    def test_the_fingerprint_is_unchanged_by_the_pathspec(self) -> None:
        """AC-04: an .saipen-only change never moves the identity, before or after."""
        repo = self.tmp / "repo"
        _init_repo(repo)
        (repo / "code.py").write_text("x\n", encoding="utf-8")
        (repo / ".saipen").mkdir()
        (repo / ".saipen" / "STATE.md").write_text("one\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "base")

        before = compute_source_identity(repo)
        (repo / ".saipen" / "STATE.md").write_text("two\n", encoding="utf-8")
        after = compute_source_identity(repo)

        self.assertEqual(before.source_tree_fingerprint, after.source_tree_fingerprint)
        self.assertEqual(before.source_head, after.source_head)

    def test_declared_nested_repository_keeps_its_own_saipen_boundary(self) -> None:
        """AC-05: the pathspec also reaches the nested binding, on purpose.

        `_nested_binding` does not filter the nested listing -- it hashes
        `raw_delta + b"\\0" + untracked` verbatim. So excluding the nested
        repository's own `.saipen` here CHANGES the outer fingerprint relative
        to the pre-T-1900 function. That direction is correct (a nested
        project's runtime churn is not the outer project's source, and the
        outer `.saipen` was already excluded by `_is_saipen_path`), but it is a
        semantic change, not a cost change, so it is pinned rather than
        assumed. Nested SOURCE must keep binding in the same direction.
        """
        outer = self.tmp / "outer"
        _init_repo(outer)
        inner = outer / "inner"
        inner.mkdir()
        _init_repo(inner)
        (inner / "code.py").write_text("a\n", encoding="utf-8")
        _git(inner, "add", "-A")
        _git(inner, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "base")
        (outer / "outer.py").write_text("o\n", encoding="utf-8")
        (outer / ".gitignore").write_text("inner/\n", encoding="utf-8")
        (outer / ".saipen").mkdir()
        (outer / ".saipen" / "source-nested-repos.json").write_text(
            '{"schema_version":1,"nested_repos":["inner"]}', encoding="utf-8"
        )
        _git(outer, "add", "-A")
        _git(outer, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "base")

        baseline = compute_source_identity(outer)

        (inner / ".saipen").mkdir()
        (inner / ".saipen" / "STATE.md").write_text("runtime\n", encoding="utf-8")
        with_runtime = compute_source_identity(outer)
        self.assertEqual(
            baseline.source_tree_fingerprint,
            with_runtime.source_tree_fingerprint,
            "a nested repository's own .saipen is its runtime, not the outer source",
        )
        self.assertEqual(
            _untracked(_git_delta_listing(inner)),
            [],
            "the nested listing must not carry the nested runtime tree",
        )

        (inner / "code2.py").write_text("real\n", encoding="utf-8")
        with_source = compute_source_identity(outer)
        self.assertNotEqual(
            baseline.source_tree_fingerprint,
            with_source.source_tree_fingerprint,
            "nested SOURCE must still bind into the outer identity",
        )
        (inner / "code2.py").unlink()

        (inner / ".saipen-src").mkdir()
        (inner / ".saipen-src" / "keep.py").write_text("k\n", encoding="utf-8")
        with_lookalike = compute_source_identity(outer)
        self.assertNotEqual(
            baseline.source_tree_fingerprint,
            with_lookalike.source_tree_fingerprint,
            "lookalike names stay ordinary nested source",
        )


if __name__ == "__main__":
    unittest.main()
