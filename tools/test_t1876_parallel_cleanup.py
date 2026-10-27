"""T-1876 / SRC-304 R005-R008: the family's teardown is concurrent, not serial.

`run_family` reclaims one sandbox per shard in its `finally`. Each tree is a
full copy of the subject, so the loop was serial, purely I/O, and grew with
the shard count: measured on the live tree, `cleanup_wall_s` was 116 s at 6
shards and 286 s at 12, while the shard split's own execution saving between
those two runs was 401 s. The teardown paid a large part of it back.

These tests pin the contract the rewrite must keep, not just its speed:

1. Every path is reclaimed, and a path that survives is REPORTED -- a failed
   reclaim is a leak, never a silent success.
2. Reclamation stays per-tree: one stuck tree neither strands nor hides the
   others. That independence is what makes concurrency safe, because `reclaim`
   already owned exactly one path.
3. The work overlaps. Measured as in-flight count, never as elapsed time: a
   serial loop cannot have two reclaims open at once, whatever the clock says.

Test 3 is the red-before-green oracle: it fails against the serial
`[item for item in paths if not reclaim(item)]` loop at any tree count.
"""

from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402


class _Overlap:
    """A reclaim stand-in that records how many calls were open at once."""

    def __init__(self, delay: float = 0.15, fail: tuple[str, ...] = ()) -> None:
        self.delay = delay
        self.fail = set(fail)
        self.lock = threading.Lock()
        self.in_flight = 0
        self.peak = 0
        self.seen: list[str] = []

    def __call__(self, path: Path) -> bool:
        name = Path(path).name
        with self.lock:
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
            self.seen.append(name)
        try:
            time.sleep(self.delay)
            return name not in self.fail
        finally:
            with self.lock:
                self.in_flight -= 1


class ReclaimAllTests(unittest.TestCase):
    def _paths(self, count: int) -> list[Path]:
        return [Path(f"/sandbox/saipen-core-unit-{index:02d}") for index in range(count)]

    def test_every_path_is_reclaimed_and_overlapping(self):
        overlap = _Overlap()
        paths = self._paths(4)
        with mock.patch.object(core_unit, "reclaim", side_effect=overlap):
            leaked = core_unit.reclaim_all(paths)
        self.assertEqual(leaked, [])
        self.assertEqual(sorted(overlap.seen), sorted(path.name for path in paths))
        self.assertGreaterEqual(
            overlap.peak, 2,
            "reclaim calls never overlapped; the teardown is still serial",
        )

    def test_a_surviving_tree_is_reported_not_swallowed(self):
        paths = self._paths(3)
        stuck = paths[1].name
        overlap = _Overlap(delay=0.0, fail=(stuck,))
        with mock.patch.object(core_unit, "reclaim", side_effect=overlap):
            leaked = core_unit.reclaim_all(paths)
        self.assertEqual(leaked, [str(paths[1])])
        self.assertEqual(len(overlap.seen), 3, "a failure must not stop the others")

    def test_a_stuck_tree_does_not_delay_the_others(self):
        paths = self._paths(3)
        blocked = paths[0].name
        release = threading.Event()
        started = threading.Event()

        def reclaim_with_one_block(path: Path) -> bool:
            if Path(path).name == blocked:
                started.set()
                release.wait(5.0)
                return False
            return True

        with mock.patch.object(core_unit, "reclaim", side_effect=reclaim_with_one_block):
            timer = threading.Timer(0.05, release.set)
            timer.start()
            try:
                leaked = core_unit.reclaim_all(paths)
            finally:
                release.set()
                timer.cancel()
        self.assertEqual(leaked, [str(paths[0])])

    def test_no_paths_is_no_work_and_no_thread_pool(self):
        self.assertEqual(core_unit.reclaim_all([]), [])

    def test_a_real_run_still_reclaims_every_sandbox_it_created(self):
        """The rewrite is inside `run_family`: prove it there, not only alone."""
        import test_t1505_core_unit_sandbox_reclaim as reclaim_cases

        case = reclaim_cases.RunFamilyLeavesNothingTests(
            "test_a_whole_run_leaves_no_sandbox"
        )
        for jobs in (1, 3):
            with self.subTest(jobs=jobs):
                run, created, left = case.run_small(jobs)
                self.assertEqual(run["status"], "PASS", run)
                self.assertEqual(left, [])
                self.assertEqual(run["sandboxes_leaked"], [])
                self.assertTrue(created, "the run must have made a sandbox")


if __name__ == "__main__":
    unittest.main()
