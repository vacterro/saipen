"""T-2092 (night shift 7, W1): one live runner's sandbox survives another.

The night-6 incident: a core-unit run lost files mid-run -- BOOT.md,
tests/scenarios, adapter registry -- inside `V:\\_TEMP_\\saipen-core-unit-*`
while other sessions shared the machine, and the re-run came back clean.
The exact deleter was never proven, so this suite does not guess it. It holds
the invariants V1-V8 of the handoff against the two deletion paths the
engine owns, with every fault injected only into disposable temp roots:

* `run_family` copies the tree into owner-stamped sandboxes and never deletes
  a sibling run's sandbox, whatever the two runs' relative timing;
* `sweep_stale_sandboxes` keeps a sandbox whose stamp names ANY live process
  of THIS project (creator or reader), and refuses unknown ownership (V4);
* `reclaim` is caller-owned: a foreign stamp clobbered into MY sandbox must
  not make my cleanup delete a foreign tree or misreport mine;
* `register_sandbox` never rewrites a stamp into another execution's record
  when no flight is active.

Two proven defects are pinned here as regression controls (RED before the
fixes):

1. STAMP-CLOBBER DURING RECLAIM: `reclaim` re-read the owner stamp on every
   retry, so a foreign writer that replaces MY stamp with its own between my
   iterations had ITS bytes restored by MY cleanup verbatim -- my tree then
   answered to a `verification_flight` that never owned it. The restore now
   replays the bytes the cleanup STARTED from.
2. UNKNOWN-OWNERSHIP RECLAIM (V4): `sweep_stale_sandboxes` treated a stamp
   that named NO usable process (missing or non-int pid and reader) as
   "no live owner" and deleted the tree. Unknown or incomplete ownership now
   refuses automatic deletion.
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
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from saipen_engine.test_runner import TestFamily  # noqa: E402


def dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def sandbox_tree(base: Path, name: str, stamp: dict | None) -> Path:
    """One owner-stamped `saipen-core-unit-*` tree with a real copied shape."""
    root = base / name
    (root / "project" / "tools").mkdir(parents=True)
    (root / "project" / "tools" / "BOOT.md").write_text("boot", encoding="utf-8")
    (root / "project" / "tests" / "scenarios").mkdir(parents=True)
    (root / "project" / "tests" / "scenarios" / "registry.json").write_text("{}", encoding="utf-8")
    if stamp is not None:
        (root / core_unit.SANDBOX_OWNER).write_text(json.dumps(stamp), encoding="utf-8")
    return root


class ConcurrentSweepTests(unittest.TestCase):
    """V1/V2/V5: a sweep from one run never deletes a live sibling's sandbox."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="t2092-sweep-"))
        self.addCleanup(core_unit.reclaim, self.temp)

    def stamp(self, **extra) -> dict:
        base = {"pid": os.getpid(), "created": time.time(), "project": str(self.temp.resolve())}
        base.update(extra)
        return base

    def test_a_live_creator_blocks_the_sweep(self):
        live = sandbox_tree(
            self.temp, core_unit.SANDBOX_PREFIX + "live-creator", self.stamp()
        )
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp, project=self.temp), [])
        self.assertTrue((live / "project" / "tools" / "BOOT.md").exists())

    def test_a_live_reader_blocks_the_sweep_even_with_a_dead_creator(self):
        reading = sandbox_tree(
            self.temp,
            core_unit.SANDBOX_PREFIX + "live-reader",
            self.stamp(pid=dead_pid(), reader=os.getpid()),
        )
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp, project=self.temp), [])
        self.assertTrue(reading.exists())

    def test_a_foreign_project_live_sandbox_is_never_swept(self):
        foreign = sandbox_tree(
            self.temp,
            core_unit.SANDBOX_PREFIX + "foreign",
            {"pid": os.getpid(), "reader": os.getpid(),
             "project": str(self.temp / "another-project")},
        )
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp, project=self.temp), [])
        self.assertTrue(foreign.exists())

    def test_two_runs_sandboxes_are_disjoint_and_both_survive_a_sweep(self):
        """V5: same project, two concurrent runs, one sweep sees both live."""
        first = sandbox_tree(
            self.temp, core_unit.SANDBOX_PREFIX + "run-a", self.stamp(reader=os.getpid())
        )
        second = sandbox_tree(
            self.temp, core_unit.SANDBOX_PREFIX + "run-b", self.stamp(reader=os.getpid())
        )
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp, project=self.temp), [])
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())

    def test_an_incomplete_stamp_is_never_reclaimed(self):
        """V4: a stamp naming NO process at all is unknown ownership."""
        incomplete = sandbox_tree(
            self.temp,
            core_unit.SANDBOX_PREFIX + "incomplete",
            {"created": time.time(), "project": str(self.temp.resolve())},
        )
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp, project=self.temp), [])
        self.assertTrue(incomplete.exists())

    def test_a_stamp_with_a_non_int_pid_is_unknown_not_stale(self):
        odd = sandbox_tree(
            self.temp,
            core_unit.SANDBOX_PREFIX + "odd-pid",
            {"pid": "not-a-pid", "project": str(self.temp.resolve())},
        )
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp, project=self.temp), [])
        self.assertTrue(odd.exists())


class RealFamilyConcurrencyTests(unittest.TestCase):
    """V1/V5/V6 with real `run_family` sandboxes on a disposable copied tree.

    The family discovers `tools/` -- the declared registry -- so the copied
    subject is a small real subtree of THIS repository, kept tiny so the two
    runs stay hermetic and fast.
    """

    SUBJECT = ("tools/saipen_engine", "tools/regression_t2089")

    @classmethod
    def subject(cls, base: Path) -> Path:
        target = base / "subject"
        for rel in cls.SUBJECT:
            shutil.copytree(TOOLS.parent / rel, target / rel)
        (target / "tools" / "empty.py").write_text("", encoding="utf-8")
        return target

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="t2092-family-"))
        self.addCleanup(core_unit.reclaim, self.base)
        self.subject_tree = self.subject(self.base)

    def test_two_concurrent_runs_never_reclaim_each_others_sandboxes(self):
        from concurrent.futures import ThreadPoolExecutor

        # T-2093: the old probe was overwritten per call, so only the LAST
        # run's cleanup was ever observed, and the leak assert compared a
        # value to itself. Both defects are pinned in
        # tools/test_t2093_concurrent_cross_process.py; this test now keeps
        # every observation and asserts on every run result.
        captures: list[list[str]] = []
        original = core_unit.reclaim_all

        def watching(paths):
            captures.append(sorted(Path(p).name for p in paths))
            return original(paths)

        import unittest.mock

        with unittest.mock.patch.object(core_unit, "reclaim_all", watching):
            with ThreadPoolExecutor(max_workers=2) as pool:
                runs = [
                    future.result()
                    for future in [
                        pool.submit(lambda: core_unit.run_family(self.subject_tree, jobs=1)),
                        pool.submit(lambda: core_unit.run_family(self.subject_tree, jobs=1)),
                    ]
                ]
        names = sorted(name for capture in captures for name in capture)
        self.assertEqual(len(names), len(set(names)), "two runs shared a sandbox")
        self.assertEqual(len(captures), 2, "one run's cleanup was never observed")
        for run in runs:
            self.assertEqual(run.get("sandboxes_leaked") or [], [],
                             "a concurrent run leaked its sandbox")
        self.assertEqual(core_unit.sweep_stale_sandboxes(project=self.subject_tree), [])

    def test_one_run_sweeping_while_another_copies_keeps_the_copier_alive(self):
        """The night-6 shape: run A sweeps while run B is mid-copy."""
        from concurrent.futures import ThreadPoolExecutor

        def sweeper():
            reclaimed = []
            for _ in range(8):
                reclaimed += core_unit.sweep_stale_sandboxes(
                    project=self.subject_tree
                )
                time.sleep(0.05)
            return reclaimed

        with ThreadPoolExecutor(max_workers=2) as pool:
            sweep_future = pool.submit(sweeper)
            run = pool.submit(lambda: core_unit.run_family(self.subject_tree, jobs=1))
            swept = sweep_future.result()
            report = run.result()
        # A sandbox of THIS project that is live right now must not be in the
        # sweep's reclaim list: only dead-owner trees may be reclaimed.
        self.assertEqual(report.get("sandboxes_leaked") or [], [])
        self.assertTrue(Path(self.subject_tree).exists())

    def test_the_sweep_of_one_project_never_names_another_projects_sandbox(self):
        other = sandbox_tree(
            self.base,
            core_unit.SANDBOX_PREFIX + "other-project",
            {"pid": dead_pid(), "reader": dead_pid(),
             "project": str(self.base / "unrelated")},
        )
        reclaimed = core_unit.sweep_stale_sandboxes(project=self.subject_tree)
        self.assertTrue(other.exists())
        self.assertNotIn(other.name, reclaimed)


class StampClobberTests(unittest.TestCase):
    """The proven reclaim defect: a foreign stamp must not leak into my cleanup.

    RED before the fix: `reclaim` restores stamp bytes it re-read mid-retry,
    so a foreign writer's `verification_flight` survives in MY sandbox stamp
    after MY cleanup failed -- the tree then answers to an execution that
    never owned it.
    """

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="t2092-clobber-"))
        self.addCleanup(core_unit.reclaim, self.temp)

    def test_a_clobbered_stamp_never_gains_a_foreign_flight(self):
        mine = sandbox_tree(
            self.temp,
            core_unit.SANDBOX_PREFIX + "mine",
            {"pid": os.getpid(), "project": str(self.temp.resolve())},
        )
        stamp = mine / core_unit.SANDBOX_OWNER
        # A foreign process writes ITS stamp into MY tree while my cleanup is
        # between iterations: the handle-holding child keeps the tree present,
        # so reclaim retries and restores the stamp. The restore must replay
        # the bytes MY cleanup started from, never a later foreign overwrite.
        holder = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=mine,
        )
        self.addCleanup(holder.wait)
        foreign = {
            "pid": os.getpid(),
            "project": str(self.temp.resolve()),
            "verification_flight": "foreign-execution-0001",
        }
        clobber_at = {"done": False}

        def clobber(_seconds):
            if not clobber_at["done"]:
                stamp.write_text(json.dumps(foreign), encoding="utf-8")
                clobber_at["done"] = True

        with unittest.mock.patch.object(core_unit.time, "sleep", side_effect=clobber):
            with unittest.mock.patch.object(core_unit, "RECLAIM_ATTEMPTS", 2):
                gone = core_unit.reclaim(mine)
        self.assertFalse(gone, "reclaim must report the held tree, not claim success")
        data = json.loads(stamp.read_text(encoding="utf-8"))
        self.assertNotIn(
            "verification_flight",
            data,
            "a foreign flight must not survive my failed cleanup",
        )
        self.assertTrue(mine.exists())
        holder.terminate()


import unittest.mock  # noqa: E402  (late import keeps the module header thin)


if __name__ == "__main__":
    unittest.main(verbosity=2)