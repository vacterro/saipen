"""T-2093: the cleanup grammar must refuse unproven ownership (fail-closed).

A stamp that cannot name its project, or names process fields the grammar
cannot hold, is UNKNOWN ownership: the sweep must leave the sandbox alone
instead of deleting on evidence it never had. Night 8 reproduction matrix
(four independent scenarios) plus the legitimate-liveness and legacy cases
that keep the sweep actually reclaiming dead trees.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.saipen_engine.core_unit import (
    LEGACY_SANDBOX_AGE_S,
    SANDBOX_PREFIX,
    new_sandbox_root,
    sweep_stale_sandboxes,
)


def _dead_pid() -> int:
    """A process id that is provably not running on this OS right now.

    Spawn-and-reap beats pid scanning: the id is ours, recently exited, and
    `pid_alive` is checked before use so a scheduler that hands it to a new
    process fails the test loudly instead of passing for the wrong reason.
    """
    import subprocess

    if os.name == "nt":
        proc = subprocess.Popen(
            ["cmd", "/c", "exit 7"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            [sys.executable, "-c", "import os; os._exit(7)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    proc.wait()
    if proc.returncode == 7 and not _pid_live(proc.pid):
        return proc.pid
    return _scan_dead()


def _pid_live(pid: int) -> bool:
    from tools.saipen_engine.core_unit import pid_alive

    return pid_alive(pid)


def _scan_dead() -> int:
    for pid in range(4, 4000):
        if not _pid_live(pid):
            return pid
    raise RuntimeError("no dead pid found for the grammar tests")


def _stamp(root: Path, **fields) -> None:
    payload = {
        "pid": os.getpid(),
        "created": time.time(),
        "spawn_phase": "COPYING",
        "project": str(Path(__file__).resolve().parents[1]),
    }
    payload.update(fields)
    (root / "owner.json").write_text(json.dumps(payload), encoding="utf-8")


class OwnerStampGrammarTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="t2093-grammar-"))
        self.project = str(Path(__file__).resolve().parents[1])
        self.dead = _dead_pid()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp, ignore_errors=True)

    def _sandbox(self, name: str = "saipen-core-unit-live") -> Path:
        root = self.temp / name
        (root / "project").mkdir(parents=True)
        return root

    def sweep(self):
        return sweep_stale_sandboxes(
            temp_root=self.temp, project=self.project, now=time.time()
        )

    # 1. A stamp with no project at all is UNKNOWN under an explicit filter.
    def test_missing_project_is_not_reclaimed(self):
        root = self._sandbox()
        _stamp(root, pid=self.dead, project=None)
        del_field = json.loads((root / "owner.json").read_text())
        del_field.pop("project")
        (root / "owner.json").write_text(json.dumps(del_field))
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    # 2. A non-string project (null/number/object) is UNKNOWN, not "same".
    def test_null_project_is_not_reclaimed(self):
        root = self._sandbox()
        _stamp(root, pid=self.dead, project=None)
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    def test_numeric_project_is_not_reclaimed(self):
        root = self._sandbox()
        _stamp(root, pid=self.dead, project=12345)
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    # 3/4. Half-malformed process fields never license a delete.
    def test_dead_creator_with_malformed_reader_is_kept(self):
        root = self._sandbox()
        _stamp(root, pid=self.dead, reader="not-a-pid")
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    def test_malformed_creator_with_dead_reader_is_kept(self):
        root = self._sandbox()
        _stamp(root, pid="not-a-pid", reader=self.dead)
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    def test_bool_creator_is_not_a_live_guard(self):
        root = self._sandbox()
        _stamp(root, pid=True, reader=self.dead)
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    # 5. The legitimate dead case still reclaims: fail-closed, not frozen.
    def test_dead_creator_and_dead_reader_reclaim(self):
        root = self._sandbox()
        _stamp(root, pid=self.dead, reader=_dead_pid())
        swept = self.sweep()
        self.assertIn(root.name, swept)
        self.assertFalse(root.exists())

    # 6/7. Real live processes protect the tree, whatever else the stamp says.
    def test_live_creator_protects(self):
        root = self._sandbox()
        _stamp(root, pid=os.getpid())
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    def test_live_reader_protects(self):
        root = self._sandbox()
        _stamp(root, pid=self.dead, reader=os.getpid())
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    # 8. Legitimate COPYING phase without a reader must still sweep-check by
    # the creator alone (documented spawn phase: reader arrives later).
    def test_copying_phase_without_reader_sweeps_on_dead_creator(self):
        root = self._sandbox()
        _stamp(root, pid=self.dead, reader=None)
        payload = json.loads((root / "owner.json").read_text())
        # A COPYING-phase stamp carries NO reader key at all: `reader: null`
        # is itself a damaged stamp the V4 grammar keeps (T-2092 regression).
        payload.pop("reader")
        (root / "owner.json").write_text(json.dumps(payload))
        self.assertEqual(payload["spawn_phase"], "COPYING")
        self.assertIn(root.name, self.sweep())
        self.assertFalse(root.exists())

    # 9. Corrupt owner JSON never licenses a destructive cleanup.
    def test_corrupt_owner_json_is_kept(self):
        root = self._sandbox()
        (root / "owner.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    # 10. A different project's sandbox is never ours to delete.
    def test_cross_project_sandbox_is_kept(self):
        root = self._sandbox()
        _stamp(root, pid=self.dead, reader=_dead_pid(),
               project="C:/definitely/another/tree")
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    # 11. T-2094: three ownership states must not collapse into two. An ABSENT
    # stamp is a legacy sandbox; a PRESENT but non-stamp payload (JSON null,
    # a list, a scalar) is damaged ownership. Only the first has a compatible
    # age-based policy, and only WITHOUT an explicit project filter.
    def _age(self, root: Path, seconds: float) -> None:
        moment = time.time() - seconds
        os.utime(root, (moment, moment))

    def test_absent_stamp_legacy_sandbox_is_kept_under_a_project_filter(self):
        root = self._sandbox("saipen-core-unit-unstamped")
        self._age(root, LEGACY_SANDBOX_AGE_S + 600)
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists(),
                        "a project-scoped sweep has no proof this unstamped "
                        "legacy tree belongs to the project")

    def test_json_null_stamp_is_kept_under_a_project_filter(self):
        root = self._sandbox("saipen-core-unit-null")
        (root / "owner.json").write_text("null", encoding="utf-8")
        self._age(root, LEGACY_SANDBOX_AGE_S + 600)
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists(),
                        "JSON null is a PRESENT malformed stamp, not an absent one")

    def test_json_null_stamp_is_kept_without_a_project_filter(self):
        root = self._sandbox("saipen-core-unit-null-global")
        (root / "owner.json").write_text("null", encoding="utf-8")
        self._age(root, LEGACY_SANDBOX_AGE_S + 600)
        self.assertEqual(sweep_stale_sandboxes(temp_root=self.temp), [])
        self.assertTrue(root.exists())

    def test_a_non_object_stamp_is_kept(self):
        for index, payload in enumerate(("[]", "[1, 2, 3]", '"owner"', "42")):
            with self.subTest(payload=payload):
                root = self._sandbox(f"saipen-core-unit-scalar-{index}")
                (root / "owner.json").write_text(payload, encoding="utf-8")
                self._age(root, LEGACY_SANDBOX_AGE_S + 600)
                self.assertEqual(self.sweep(), [])
                self.assertTrue(root.exists())

    def test_an_empty_object_stamp_is_kept(self):
        root = self._sandbox("saipen-core-unit-empty")
        (root / "owner.json").write_text("{}", encoding="utf-8")
        self._age(root, LEGACY_SANDBOX_AGE_S + 600)
        self.assertEqual(self.sweep(), [])
        self.assertTrue(root.exists())

    def test_a_truly_absent_stamp_still_ages_out_without_a_project_filter(self):
        # The compatible policy for a genuine pre-T-1505 sandbox stays exactly
        # where it was: global sweep, project/ present, older than the age.
        root = self._sandbox("saipen-core-unit-legacy")
        self._age(root, LEGACY_SANDBOX_AGE_S + 60)
        self.assertEqual(sweep_stale_sandboxes(temp_root=self.temp), [root.name])
        self.assertFalse(root.exists())

    def test_concurrent_sweeps_keep_a_live_stamp(self):
        from concurrent.futures import ThreadPoolExecutor

        root = self._sandbox("saipen-core-unit-concurrent")
        _stamp(root, pid=os.getpid())
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.sweep(), range(4)))
        self.assertEqual(results, [[], [], [], []])
        self.assertTrue(root.exists())

    # Regression: the fresh-stamp shape `new_sandbox_root` writes must stay
    # sweep-eligible only through the same grammar (live creator -> kept).
    def test_fresh_sandbox_stamp_shape_survives_sweep(self):
        root = new_sandbox_root(self.project)
        try:
            root2 = self.temp / "saipen-core-unit-newroot"
            root2.mkdir()
            stamp = json.loads((root / "owner.json").read_text())
            _stamp(root2, **stamp)
            self.assertEqual(
                sweep_stale_sandboxes(
                    temp_root=self.temp, project=self.project
                ),
                [],
            )
            self.assertTrue(root2.exists())
        finally:
            import shutil

            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
