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

import contextlib
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
from unittest import mock

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

    def held_within(self, path: Path, seconds: float = 30.0) -> bool:
        """Whether a holder has taken the tree inside the bound.

        T-1597: the control used to sleep 0.5 s and assume the child had
        started. Nothing guarantees that under six shards, so the assumption
        was the flake: a tree that was not held yet was reclaimed, and the
        assertion "a held tree is reported, not raised" failed for a reason it
        never named. Poll the real condition instead, and name it on failure.
        """
        deadline = time.monotonic() + seconds
        while path.exists() and time.monotonic() < deadline:
            if not core_unit.reclaim(path):
                return True
            time.sleep(0.05)
        return False

    def sweep_within(self, root: Path, seconds: float = 30.0) -> list[str]:
        """Sweep until the dead owner's handle is released, or report empty.

        Windows releases a just-exited process's directory handle on its own
        schedule; `reclaim` is documented to retry a few times and then
        REPORT. One sweep taken at the instant `wait()` returned is therefore
        a race, and the retry is bounded so a sandbox that is never reclaimed
        still fails loudly.
        """
        deadline = time.monotonic() + seconds
        swept: list[str] = []
        while time.monotonic() < deadline:
            swept = core_unit.sweep_stale_sandboxes(root)
            if swept:
                return swept
            time.sleep(0.2)
        return swept

    def test_a_held_sandbox_is_reported_then_swept_once_its_owner_is_gone(self):
        temp = Path(tempfile.mkdtemp(prefix="t1505-held-"))
        self.addCleanup(core_unit.reclaim, temp)
        sandbox = temp / (core_unit.SANDBOX_PREFIX + "held")
        sandbox.mkdir()
        (sandbox / core_unit.SANDBOX_OWNER).write_text(
            json.dumps({"pid": dead_pid()}), encoding="utf-8"
        )
        holder = self.hold(sandbox)
        self.assertTrue(self.held_within(sandbox), "the holder never took the sandbox")
        self.assertTrue(sandbox.exists())
        holder.kill()
        holder.wait()
        self.assertEqual(self.sweep_within(temp), [sandbox.name])
        self.assertFalse(sandbox.exists())

    def test_waiting_for_a_sweep_never_reclaims_a_live_owner(self):
        """The retry waits for the handle; it must not wait the owner away."""
        temp = Path(tempfile.mkdtemp(prefix="t1505-live-"))
        self.addCleanup(core_unit.reclaim, temp)
        sandbox = temp / (core_unit.SANDBOX_PREFIX + "live")
        sandbox.mkdir()
        (sandbox / core_unit.SANDBOX_OWNER).write_text(
            json.dumps({"pid": os.getpid()}), encoding="utf-8"
        )
        self.assertEqual(self.sweep_within(temp, seconds=1.0), [])
        self.assertTrue(sandbox.exists())


class RunFamilyLeavesNothingTests(unittest.TestCase):
    """A real (small) run through `run_family`, whole and sharded."""

    def run_small(self, jobs: int) -> tuple[dict, list[Path], list[str]]:
        created: list[Path] = []
        new_sandbox_root = core_unit.new_sandbox_root

        def track_sandbox() -> Path:
            sandbox = new_sandbox_root()
            created.append(sandbox)
            self.addCleanup(core_unit.reclaim, sandbox)
            return sandbox

        small = TestFamily(
            core_unit.FAMILY_NAME,
            (sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools",
             "-p", "test_hermetic_env.py", "-v"),
            600,
        )
        with contextlib.ExitStack() as patches:
            patches.enter_context(mock.patch.object(core_unit, "family", return_value=small))
            patches.enter_context(
                mock.patch.object(core_unit, "new_sandbox_root", side_effect=track_sandbox)
            )
            run = core_unit.run_family(TOOLS.parent, jobs=jobs)
        # Other core-unit runs share the temp root. Inspect only this invocation's
        # creations, independently of its self-reported sandboxes_leaked result.
        return run, created, sorted(sandbox.name for sandbox in created if sandbox.exists())

    def assert_run_leaves_no_sandbox(self, jobs: int, *, shards: int | None = None) -> None:
        run, created, left = self.run_small(jobs)
        self.assertEqual(run["status"], "PASS", run)
        self.assertEqual(left, [])
        self.assertEqual(run["sandboxes_leaked"], [])
        if shards is not None:
            # One tracked sandbox per shard that actually runs. The fixture
            # family discovers ONE module, so a sharded run has one shard to
            # run: `plan_shards` drops a shard that drew no module (an empty
            # shard exits 5, "no tests ran") and a sandbox with no shard to run
            # is a copy of the tree paid for nothing. Counted here rather than
            # inside `run_small`, because the two controls below replace
            # `run_family` with a stub that makes its own sandboxes.
            self.assertEqual(len(created), shards, "every run/shard must have a tracked sandbox")

    def test_a_whole_run_leaves_no_sandbox(self):
        self.assert_run_leaves_no_sandbox(1, shards=1)

    def test_a_sharded_run_leaves_no_sandbox(self):
        self.assert_run_leaves_no_sandbox(2, shards=1)

    def test_unrelated_sandboxes_before_and_during_a_run_are_not_its_leaks(self):
        new_foreign_sandbox = core_unit.new_sandbox_root
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                foreign = [new_foreign_sandbox()]
                self.addCleanup(core_unit.reclaim, foreign[0])

                def run_with_foreign_sandbox(_root, *, jobs):
                    # Bypass the tested invocation's factory, as another process
                    # creating a sandbox in the same temp directory would do.
                    foreign.append(new_foreign_sandbox())
                    self.addCleanup(core_unit.reclaim, foreign[-1])
                    for _ in range(jobs):
                        sandbox = core_unit.new_sandbox_root()
                        self.assertTrue(core_unit.reclaim(sandbox))
                    return {"status": "PASS", "sandboxes_leaked": []}

                with mock.patch.object(
                    core_unit, "run_family", side_effect=run_with_foreign_sandbox
                ):
                    self.assert_run_leaves_no_sandbox(jobs)
                self.assertTrue(all(sandbox.exists() for sandbox in foreign))

    def test_an_unreported_own_leak_is_still_detected_including_the_last_shard(self):
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                created: list[Path] = []

                def run_with_unreported_leak(_root, *, jobs):
                    created.extend(core_unit.new_sandbox_root() for _ in range(jobs))
                    for sandbox in created[:-1]:
                        self.assertTrue(core_unit.reclaim(sandbox))
                    return {"status": "PASS", "sandboxes_leaked": []}

                leak = mock.patch.object(
                    core_unit, "run_family", side_effect=run_with_unreported_leak
                )
                with leak, self.assertRaises(AssertionError) as caught:
                    self.assert_run_leaves_no_sandbox(jobs)
                self.assertIn(created[-1].name, str(caught.exception))
                self.assertTrue(created[-1].exists())


if __name__ == "__main__":
    unittest.main()
