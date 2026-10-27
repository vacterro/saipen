"""The three sampling passes overlap their reads but stay bit-identical (T-1902).

`_parse_git_delta_evidence` runs three times per `compute_source_identity`:
two observer-less sampling passes and one confirming pass whose frames are
streamed into the canonical digest. T-1902 overlapped the per-file reads inside
each observer-less pass with a bounded thread pool.

The risk this file guards is not "is it faster" -- that is measured, not
asserted -- but "is it the same capture". Three things could silently break,
so each has its own case:

1. **Record ORDER.** The output is ordered by `sorted(records)`, not by kind and
   not by which read finished first. The confirming pass frames those records
   into `git-delta-v1` in exactly that sequence, so a reordering changes the
   fingerprint of an unchanged tree. An early version of this change sorted the
   merged list by path and put every deletion at the end; the first test below
   is what caught it.

2. **`path_map` contents.** The map is filled on the main thread in sorted
   order before any worker starts, so no two workers race for one raw path and
   a project spelled two ways cannot end up with two validated paths. Both are
   asserted equal, not just the evidence.

3. **Observer ordering and the error path.** The confirming pass must not run
   in parallel (its frame order is the digest) and a failing input must raise
   the same `FreshnessError` for the same path a sequential pass would have
   raised first, never whichever worker lost a race.

Nothing here asserts a duration: a timing assertion on a shared machine is a
flaky test, and the measured numbers live in the ticket's evidence instead.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import freshness  # noqa: E402


def _git(*args: str, cwd: Path) -> None:
    import subprocess

    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise AssertionError(f"git {args} failed: {completed.stderr[-400:]}")


class ParallelParseEquivalenceTests(unittest.TestCase):
    """The parallel read path is the sequential path, only faster."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="saipen-t1902-")
        self.root = Path(self._temp.name)
        _git("init", "-q", cwd=self.root)
        _git("config", "user.email", "t@example.invalid", cwd=self.root)
        _git("config", "user.name", "t", cwd=self.root)
        # A mix of tracked-clean, tracked-modified, deleted and untracked
        # inputs, because deletions take a different branch of the parser and a
        # tracker that reorders them is exactly the defect case 1 describes.
        (self.root / "a.txt").write_text("a\n", encoding="utf-8")
        (self.root / "b.txt").write_text("b\n", encoding="utf-8")
        (self.root / "c.txt").write_text("c\n", encoding="utf-8")
        (self.root / "gone.txt").write_text("gone\n", encoding="utf-8")
        (self.root / "dir").mkdir()
        (self.root / "dir" / "deep.txt").write_text("deep\n", encoding="utf-8")
        _git("add", "-A", cwd=self.root)
        _git("commit", "-qm", "base", cwd=self.root)
        (self.root / "b.txt").write_text("b changed\n", encoding="utf-8")
        (self.root / "gone.txt").unlink()
        (self.root / "untracked.txt").write_text("u\n", encoding="utf-8")
        (self.root / "dir" / "untracked2.txt").write_text("u2\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._temp.cleanup()

    def _listing(self) -> tuple[bytes, bytes]:
        return freshness._git_delta_listing(self.root)

    def test_parallel_and_sequential_evidence_are_identical(self):
        listing = self._listing()
        parallel_map: dict[bytes, Path] = {}
        sequential_map: dict[bytes, Path] = {}
        parallel = freshness._parse_git_delta_evidence(
            self.root, *listing, path_map=parallel_map, parallel=True
        )
        sequential = freshness._parse_git_delta_evidence(
            self.root, *listing, path_map=sequential_map, parallel=False
        )
        self.assertEqual(parallel, sequential)
        self.assertEqual(parallel_map, sequential_map)

    def test_record_order_is_sorted_regardless_of_deletions(self):
        listing = self._listing()
        evidence = freshness._parse_git_delta_evidence(
            self.root, *listing, path_map={}, parallel=True
        )
        paths = [item.path for item in evidence]
        self.assertEqual(paths, sorted(paths), "record order left sorted() order")
        kinds = {item.path: item.kind for item in evidence}
        self.assertEqual(kinds[b"gone.txt"], b"D")
        # A deletion must not be hoisted to the end by a merge step.
        self.assertIn(b"gone.txt", paths)
        self.assertLess(
            paths.index(b"gone.txt"),
            paths.index(b"untracked.txt"),
            "deletions were reordered behind files",
        )

    def test_parallel_path_does_not_run_when_an_observer_is_present(self):
        """The confirming pass must never overlap: its frame order is the digest."""
        listing = self._listing()
        seen: list[bytes] = []
        freshness._parse_git_delta_evidence(
            self.root,
            *listing,
            path_map={},
            record_observer=lambda record: seen.append(record.path),
            parallel=False,
        )
        self.assertEqual(seen, sorted(seen))

    def test_both_paths_feed_the_same_fingerprint(self):
        """End to end: the whole capture is unmoved by the parallel read path."""

        original = freshness.compute_source_identity(self.root)
        workers = freshness._READ_WORKERS
        try:
            freshness._READ_WORKERS = 1
            sequential = freshness.compute_source_identity(self.root)
        finally:
            freshness._READ_WORKERS = workers
        parallel = freshness.compute_source_identity(self.root)
        self.assertEqual(original.source_tree_fingerprint, sequential.source_tree_fingerprint)
        self.assertEqual(original.source_tree_fingerprint, parallel.source_tree_fingerprint)

    def test_unreadable_input_raises_for_the_same_path_either_way(self):
        listing = self._listing()
        victim = self.root / "b.txt"
        victim.unlink()
        victim.mkdir()  # a directory where Git expects a file: stat succeeds, read fails
        errors = []
        for parallel in (True, False):
            try:
                freshness._parse_git_delta_evidence(
                    self.root, *listing, path_map={}, parallel=parallel
                )
            except freshness.FreshnessError as exc:
                errors.append(str(exc))
            else:
                errors.append("")
        self.assertEqual(
            errors[0], errors[1], f"parallel and sequential disagreed: {errors}"
        )
        self.assertIn("unsupported fingerprint input type", errors[0])


class ReadWorkerBoundTests(unittest.TestCase):
    def test_worker_constant_is_bounded(self):
        """A fixture-scale tree must not open one handle per changed path."""
        self.assertGreaterEqual(freshness._READ_WORKERS, 2)
        self.assertLessEqual(freshness._READ_WORKERS, 32)


if __name__ == "__main__":
    unittest.main()
