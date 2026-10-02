"""T-1505: core-unit sandboxes do not accumulate in the temp directory.

Measured 2026-09-24: 24 `saipen-core-unit-*` directories -- four sharded runs
of six shards, about 40 MB each, every one a full copy of `.saipen` -- sat in
%TEMP%. What survived in each was the read-only object store of the copied
saiwiki kitchen clone. These controls hold the three parts of the repair:

* `reclaim` removes a tree with read-only files, where `shutil.rmtree`
  stops at the first one on Windows;
* `sweep_stale_sandboxes` reclaims a sandbox whose owning run is gone and
  never touches a live run's sandbox or anything not named like one;
* `run_family` leaves no sandbox of its own behind.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
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


def read_only_tree(root: Path) -> Path:
    """A small tree shaped like a copied git object store: read-only files."""
    objects = root / "project" / ".saipen" / "kitchen" / ".git" / "objects" / "01"
    objects.mkdir(parents=True)
    for name in ("af3d38", "0caaad"):
        blob = objects / name
        blob.write_bytes(b"x")
        os.chmod(blob, stat.S_IREAD)
    return root


def dead_pid() -> int:
    """A process id that has just exited."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


class ReclaimTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="t1505-"))
        self.addCleanup(core_unit.reclaim, self.base)

    @unittest.skipUnless(os.name == "nt", "read-only files only block deletion on Windows")
    def test_plain_rmtree_cannot_remove_a_read_only_store(self):
        tree = read_only_tree(self.base / "plain")
        with self.assertRaises(PermissionError):
            shutil.rmtree(tree)
        self.assertTrue(tree.exists())

    def test_reclaim_removes_a_read_only_store(self):
        tree = read_only_tree(self.base / "reclaimed")
        self.assertTrue(core_unit.reclaim(tree))
        self.assertFalse(tree.exists())

    def test_reclaim_of_a_missing_tree_is_done(self):
        self.assertTrue(core_unit.reclaim(self.base / "never-made"))


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="t1505-sweep-"))
        self.addCleanup(core_unit.reclaim, self.temp)

    def sandbox(self, name: str, owner: dict | None) -> Path:
        root = read_only_tree(self.temp / name)
        if owner is not None:
            (root / core_unit.SANDBOX_OWNER).write_text(json.dumps(owner), encoding="utf-8")
        return root

    def test_a_dead_owners_sandbox_is_reclaimed(self):
        stale = self.sandbox(core_unit.SANDBOX_PREFIX + "dead", {"pid": dead_pid()})
        swept = core_unit.sweep_stale_sandboxes(self.temp)
        self.assertEqual(swept, [stale.name])
        self.assertFalse(stale.exists())

    def test_a_live_owners_sandbox_is_kept(self):
        live = self.sandbox(core_unit.SANDBOX_PREFIX + "live", {"pid": os.getpid()})
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp), [])
        self.assertTrue(live.exists())

    def test_an_unstamped_sandbox_waits_for_the_legacy_age(self):
        legacy = self.sandbox(core_unit.SANDBOX_PREFIX + "legacy", None)
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp), [])
        self.assertTrue(legacy.exists())
        later = time.time() + core_unit.LEGACY_SANDBOX_AGE_S + 60
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp, now=later), [legacy.name])
        self.assertFalse(legacy.exists())

    def test_nothing_outside_the_prefix_is_touched(self):
        foreign = self.sandbox("someone-elses-dir", {"pid": dead_pid()})
        not_a_sandbox = self.temp / (core_unit.SANDBOX_PREFIX + "no-project")
        not_a_sandbox.mkdir()
        later = time.time() + core_unit.LEGACY_SANDBOX_AGE_S + 60
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp, now=later), [])
        self.assertTrue(foreign.exists())
        self.assertTrue(not_a_sandbox.exists())

    def test_a_corrupt_stamp_is_left_alone(self):
        odd = self.sandbox(core_unit.SANDBOX_PREFIX + "odd", None)
        (odd / core_unit.SANDBOX_OWNER).write_text("{not json", encoding="utf-8")
        self.assertEqual(core_unit.sweep_stale_sandboxes(self.temp), [])
        self.assertTrue(odd.exists())

    def test_liveness_of_self_and_of_nothing(self):
        self.assertTrue(core_unit.pid_alive(os.getpid()))
        self.assertFalse(core_unit.pid_alive(dead_pid()))
        self.assertFalse(core_unit.pid_alive(0))


@unittest.skipUnless(os.name == "nt", "an open handle blocks deletion only on Windows")
class HeldSandboxTests(unittest.TestCase):
    """The measured failure: a process a test started still holds the sandbox."""

    HOLD = "import time; time.sleep(float(__import__('sys').argv[1]))"

    def hold(self, cwd: Path, seconds: float = 30.0) -> subprocess.Popen:
        holder = subprocess.Popen([sys.executable, "-c", self.HOLD, str(seconds)], cwd=cwd)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        time.sleep(0.5)
        return holder

    def test_temporary_directory_raises_and_leaves_a_held_sandbox_forever(self):
        left = None
        raised = False
        try:
            with tempfile.TemporaryDirectory(prefix="t1505-old-") as tmp:
                left = Path(tmp)
                holder = self.hold(left)
        except PermissionError:
            raised = True
        self.assertTrue(raised, "TemporaryDirectory cleanup raises on a held tree")
        self.addCleanup(core_unit.reclaim, left)
        holder.kill()
        holder.wait()
        self.assertTrue(left.exists(), "nothing ever reclaims it after the holder exits")

    def test_a_held_sandbox_is_reported_then_swept_once_its_owner_is_gone(self):
        temp = Path(tempfile.mkdtemp(prefix="t1505-held-"))
        self.addCleanup(core_unit.reclaim, temp)
        sandbox = temp / (core_unit.SANDBOX_PREFIX + "held")
        sandbox.mkdir()
        (sandbox / core_unit.SANDBOX_OWNER).write_text(
            json.dumps({"pid": dead_pid()}), encoding="utf-8"
        )
        holder = self.hold(sandbox)
        self.assertFalse(core_unit.reclaim(sandbox), "a held tree is reported, not raised")
        self.assertTrue(sandbox.exists())
        holder.kill()
        holder.wait()
        self.assertEqual(core_unit.sweep_stale_sandboxes(temp), [sandbox.name])
        self.assertFalse(sandbox.exists())


class RunFamilyLeavesNothingTests(unittest.TestCase):
    """A real (small) run through `run_family`, whole and sharded."""

    def run_small(self, jobs: int) -> tuple[dict, list[str]]:
        temp = Path(tempfile.gettempdir())
        before = {p.name for p in temp.glob(core_unit.SANDBOX_PREFIX + "*")}
        small = TestFamily(
            core_unit.FAMILY_NAME,
            (sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools",
             "-p", "test_hermetic_env.py", "-v"),
            600,
        )
        original = core_unit.family
        core_unit.family = lambda: small
        try:
            run = core_unit.run_family(TOOLS.parent, jobs=jobs)
        finally:
            core_unit.family = original
        after = {p.name for p in temp.glob(core_unit.SANDBOX_PREFIX + "*")}
        return run, sorted(after - before)

    def test_a_whole_run_leaves_no_sandbox(self):
        run, left = self.run_small(1)
        self.assertEqual(run["status"], "PASS", run)
        self.assertEqual(left, [])
        self.assertEqual(run["sandboxes_leaked"], [])

    def test_a_sharded_run_leaves_no_sandbox(self):
        run, left = self.run_small(2)
        self.assertEqual(run["status"], "PASS", run)
        self.assertEqual(left, [])
        self.assertEqual(run["sandboxes_leaked"], [])


if __name__ == "__main__":
    unittest.main()
