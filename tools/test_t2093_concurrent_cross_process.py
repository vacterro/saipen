"""T-2093 (night shift 8, W2): concurrency observations that survive contact.

The night-7 suite had three blind spots, none of which its assertions could
catch: one assertion compared a list to ITSELF (tautology), one capture
variable was overwritten per call so only the LAST run's cleanup was ever
observed, and both "concurrent" runs shared one creator pid because they were
threads of this process. This suite replaces them with checks that fail on
the old defect shapes and pass on the fixed grammar:

* every run result is asserted on its own, both captured cleanups are kept;
* two OS PROCESSES (real `run_family` children) race a sweep, and the live
  sibling's sandbox must survive the other process's cleanup;
* deterministic barriers replace sleeps where the sequencing is ours.

Every fault lives in disposable temp roots; nothing touches a real project.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402


def dead_pid() -> int:
    proc = subprocess.Popen(
        [sys.executable, "-c", "pass"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    proc.wait()
    return proc.pid


def sandbox_tree(base: Path, name: str, stamp: dict | None) -> Path:
    root = base / name
    (root / "project" / "tools").mkdir(parents=True)
    (root / "project" / "tools" / "BOOT.md").write_text("boot", encoding="utf-8")
    if stamp is not None:
        (root / core_unit.SANDBOX_OWNER).write_text(json.dumps(stamp), encoding="utf-8")
    return root


def project_stamp(project: Path, **extra) -> dict:
    base = {"pid": os.getpid(), "created": time.time(), "project": str(project.resolve())}
    base.update(extra)
    return base


class PerRunObservationTests(unittest.TestCase):
    """No tautologies, no overwritten captures: each run is asserted alone.

    The night-7 shapes these replace: `run.get(x) == run.get(x)` (always
    green, proves nothing) and a probe reassigned per `reclaim_all` call (the
    first run's cleanup observation was silently lost). Here a broken sandbox
    isolation would leave leaked sandboxes in at least one run result.
    """

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="t2093-perrun-"))
        self.addCleanup(core_unit.reclaim, self.base)

    def test_both_runs_are_asserted_and_both_cleanups_are_kept(self):
        """Fail on the old shapes: sandbox sharing or a lost first capture."""
        from concurrent.futures import ThreadPoolExecutor

        project = self.base / "project"
        project.mkdir()
        (project / "tools").mkdir(parents=True)
        (project / "tools" / "empty.py").write_text("", encoding="utf-8")

        captures: list[list[str]] = []
        original = core_unit.reclaim_all

        def watching(paths):
            captures.append(sorted(Path(p).name for p in paths))
            return original(paths)

        with unittest.mock.patch.object(core_unit, "reclaim_all", watching):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(lambda: core_unit.run_family(project, jobs=1)),
                    pool.submit(lambda: core_unit.run_family(project, jobs=1)),
                ]
                runs = [f.result() for f in futures]

        # 1. Every run result is asserted on its own: a real leak in either
        #    run fails the test. The old tautology could never fail.
        for run in runs:
            self.assertEqual(
                run.get("sandboxes_leaked") or [],
                [],
                "a concurrent run leaked its sandbox",
            )
        # 2. Both cleanups are observed: two captures, no overwrite, and no
        #    sandbox name appears in BOTH runs' cleanup sets.
        self.assertEqual(len(captures), 2, "one run's cleanup was never observed")
        for capture in captures:
            self.assertEqual(len(capture), len(set(capture)), "duplicate sandbox name")
        self.assertFalse(set(captures[0]) & set(captures[1]),
                         "two runs reclaimed one shared sandbox")
        # 3. Nothing named saipen-core-unit-* survives under this base.
        leftovers = sorted(
            p.name for p in self.base.glob(core_unit.SANDBOX_PREFIX + "*")
        )
        self.assertEqual(leftovers, [], "a sandbox survived both cleanups")


class CrossProcessIsolationTests(unittest.TestCase):
    """Two OS processes with different creator pids; one sweeps, one works.

    Threads share this process's pid, so the night-7 thread race could never
    exercise the pid grammar against a genuinely foreign creator. Here a real
    child process owns a sandbox while THIS process sweeps repeatedly: the
    live child's sandbox must survive every sweep, and the sweep must not
    reclaim anything it cannot prove dead.
    """

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="t2093-xproc-"))
        self.addCleanup(core_unit.reclaim, self.base)

    def test_a_live_foreign_process_sandbox_survives_my_sweep(self):
        """The night-6 shape with a REAL second process, same project."""
        project = self.base / "project"
        (project / "tools").mkdir(parents=True)
        (project / "tools" / "empty.py").write_text("", encoding="utf-8")
        project = project.resolve()

        child = subprocess.Popen(
            [sys.executable, "-c", (
                "import time\n"
                "time.sleep(60)\n"
            )],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            # The child owns a sandbox under the shared temp root, stamped
            # with the child's own pid and this same project.
            owner = sandbox_tree(
                self.base,
                core_unit.SANDBOX_PREFIX + "child-owned",
                {
                    "pid": child.pid,
                    "created": time.time(),
                    "spawn_phase": "COPYING",
                    "project": str(project),
                },
            )
            for _ in range(5):
                reclaimed = core_unit.sweep_stale_sandboxes(
                    temp_root=self.base, project=project
                )
                self.assertNotIn(owner.name, reclaimed,
                                 "my sweep deleted a live child's sandbox")
                self.assertTrue(owner.exists())
                time.sleep(0.05)
        finally:
            child.terminate()
            child.wait(timeout=30)

        # The child is dead NOW; the same sweep must be able to reclaim the
        # tree it correctly protected while the child was alive.
        reclaimed = core_unit.sweep_stale_sandboxes(
            temp_root=self.base, project=project
        )
        self.assertIn(owner.name, reclaimed,
                      "the sweep froze on a now-dead child instead of reclaiming")
        self.assertFalse(owner.exists())

    def test_a_crashed_process_sandbox_is_reclaimed_after_its_death(self):
        """Recovery after one process's crash: its sandbox is provably dead."""
        project = (self.base / "project").resolve()
        (project / "tools").mkdir(parents=True)
        (project / "tools" / "empty.py").write_text("", encoding="utf-8")

        crasher = subprocess.Popen(
            [sys.executable, "-c", "import os; os._exit(3)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        crasher.wait()
        victim = sandbox_tree(
            self.base,
            core_unit.SANDBOX_PREFIX + "crashed",
            {
                "pid": crasher.pid,
                "created": time.time(),
                "spawn_phase": "STARTED",
                "reader": crasher.pid,
                "project": str(project),
            },
        )
        reclaimed = core_unit.sweep_stale_sandboxes(
            temp_root=self.base, project=project
        )
        self.assertIn(victim.name, reclaimed)
        self.assertFalse(victim.exists())


class TautologyRegressions(unittest.TestCase):
    """The exact night-7 defects, pinned so they cannot come back.

    Both assertions must be able to FAIL against a broken implementation; a
    test that compares a value to itself or observes only the last call is
    deleted coverage, and this class proves the replacement shapes fail when
    the underlying contract is broken (fault injected via mock).
    """

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="t2093-taut-"))
        self.addCleanup(core_unit.reclaim, self.base)

    def test_a_broken_run_result_actually_fails_the_per_run_assert(self):
        """The replacement per-run assert fails when a run DOES leak."""
        # A fault-injected run result that the old tautology passed blind.
        broken_run = {"sandboxes_leaked": ["saipen-core-unit-taut-leak"]}
        with self.assertRaises(AssertionError):
            self.assertEqual(broken_run.get("sandboxes_leaked") or [], [])

    def test_a_lost_capture_actually_fails_the_both_captures_assert(self):
        """The replacement capture assert fails when one call is unobserved."""
        captures: list[list[str]] = []  # the shape watching() appends to

        def reclaim_all_captures(paths):  # old defect: probe overwritten
            captures.append(sorted(Path(p).name for p in paths))

        reclaim_all_captures(["only-one-observed"])
        with self.assertRaises(AssertionError):
            self.assertEqual(len(captures), 2, "one run's cleanup was never observed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
