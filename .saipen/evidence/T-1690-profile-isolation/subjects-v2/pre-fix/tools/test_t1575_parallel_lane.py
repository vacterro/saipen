"""T-1575 (SRC-151): while a long gate runs, the agent works; the tested tree stays put.

The operator asked that agents stop idle-waiting on long test runs and keep
working in parallel, the way this session did. Two failures bracket that:
waiting (the wall-clock is wasted) and "working" on the tree under test (the
fingerprint-bound record becomes uncitable and the whole family re-runs). The
canonical answer is one marker the running gate holds, a turn-entry projection
that names the parallel lane, and an admission refusal for in-root edits
outside `.saipen/` while the marker is live.
"""

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import admission, core_unit, inflight
from test_guard_hostile_matrix import active_project
from test_hermetic_env import isolate_host_session

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "saipen.py"


def setUpModule():
    isolate_host_session()


def _marker(root: Path, **overrides) -> Path:
    record = {
        "schema": 1, "kind": "core-unit", "ticket": "T-9", "command": "core_unit evidence",
        "pid": os.getpid(), "pid_created": inflight._process_created(os.getpid()),
        "started": time.time(), "started_utc": "2026-09-30T00:00:00Z",
    }
    record.update(overrides)
    path = root / inflight.MARKER_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


class MarkerTests(unittest.TestCase):
    def test_the_marker_lives_exactly_as_long_as_the_gate(self):
        root = active_project()
        with inflight.holding(root, "T-9", "core_unit evidence"):
            live = inflight.current(root)
            self.assertIsNotNone(live)
            self.assertEqual((live["ticket"], live["pid"]), ("T-9", os.getpid()))
        self.assertIsNone(inflight.current(root))
        self.assertFalse((root / inflight.MARKER_REL).exists())

    def test_a_stale_marker_never_freezes_the_tree(self):
        root = active_project()
        for stale in ({"pid": 2 ** 31 - 3}, {"started": time.time() - inflight.MAX_AGE_S - 60},
                      {"pid_created": 1.0}, {"schema": 2}):
            with self.subTest(stale=stale):
                _marker(root, **stale)
                self.assertIsNone(inflight.current(root))
                self.assertEqual(inflight.frozen_targets(root, ["src/app.py"]), [])

    def test_only_the_writer_removes_its_marker(self):
        root = active_project()
        path = _marker(root, pid=os.getpid() + 1)
        inflight.end(root)
        self.assertTrue(path.exists())


class GuardTests(unittest.TestCase):
    def verdict(self, root, target, action="write"):
        return admission.evaluate_admission(root, target_path=target, action=action,
                                            agent="test-agent")

    def test_in_root_edits_outside_saipen_are_refused_while_live(self):
        root = active_project()
        self.assertTrue(self.verdict(root, "src/app.py")["admitted"])
        _marker(root)
        refused = self.verdict(root, "src/app.py")
        self.assertFalse(refused["admitted"], refused)
        self.assertEqual(refused["code"], "TREE_UNDER_TEST")
        # The parallel lane stays open: reads, evidence and outside-root scratch.
        self.assertTrue(self.verdict(root, "src/app.py", action="read")["admitted"])
        self.assertTrue(self.verdict(root, ".saipen/evidence/T-9/note.txt")["admitted"])
        scratch = Path(root).parent / "scratch-copy" / "app.py"
        self.assertTrue(self.verdict(root, str(scratch))["admitted"])
        (root / inflight.MARKER_REL).unlink()
        self.assertTrue(self.verdict(root, "src/app.py")["admitted"])

    def test_a_foreign_bound_agent_cannot_edit_a_tree_under_test(self):
        """Measured 30.09.26: another project's agent edited this repo mid-run."""
        tested, foreign = active_project(), active_project()
        nested = tested / "tests" / "scenarios" / "x"
        (nested / ".saipen").mkdir(parents=True)
        target = tested / "tools" / "improve.py"
        for path in (target, nested / "src.py"):
            self.assertTrue(self.verdict(foreign, str(path))["admitted"], path)
        _marker(tested)
        for path in (target, nested / "src.py"):
            refused = self.verdict(foreign, str(path))
            self.assertEqual(refused["code"], "TREE_UNDER_TEST", refused)
            self.assertEqual(Path(refused["frozen_project"]), Path(tested))
        # Its evidence namespace stays writable for the gate's own lane.
        self.assertTrue(self.verdict(foreign, str(tested / ".saipen" / "evidence" / "a.txt"))
                        .get("code") != "TREE_UNDER_TEST")


class TurnEntryTests(unittest.TestCase):
    def cli(self, root, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
        run = subprocess.run([sys.executable, str(CLI), *args, "--json"], cwd=root,
                             capture_output=True, text=True, encoding="utf-8", env=env,
                             timeout=120)
        return json.loads(run.stdout)

    def test_continue_names_the_gate_and_the_parallel_lane(self):
        root = active_project()
        self.assertNotIn("inflight", self.cli(root, "continue"))
        sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        self.addCleanup(sleeper.wait)
        self.addCleanup(sleeper.kill)
        _marker(root, pid=sleeper.pid, pid_created=inflight._process_created(sleeper.pid))
        for verb in ("continue", "status"):
            lane = self.cli(root, verb).get("inflight")
            self.assertIsNotNone(lane, verb)
            self.assertTrue(lane["tree_frozen"])
            self.assertEqual(lane["refusal_code"], "TREE_UNDER_TEST")
            self.assertIn("never sleep-poll", lane["await"])
            self.assertTrue(any("scratch copy" in item for item in lane["parallel_lane"]))


class RunnerWiringTests(unittest.TestCase):
    def test_the_evidence_run_holds_the_marker_and_always_releases_it(self):
        root = active_project()
        seen = {}

        class Stop(Exception):
            pass

        def fake_run(*_args, **_kwargs):
            seen["live"] = inflight.current(root)
            raise Stop

        args = mock.Mock(ticket="T-9", fresh=True, timeout=None, jobs=1)
        with mock.patch.object(core_unit, "load_baseline", return_value=({}, None)), \
                mock.patch.object(core_unit, "tree_fingerprint", return_value="f"), \
                mock.patch.object(core_unit, "run_family", side_effect=fake_run), \
                self.assertRaises(Stop):
            core_unit._evidence(Path(root), args)
        self.assertIsNotNone(seen["live"])
        self.assertEqual(seen["live"]["ticket"], "T-9")
        self.assertIsNone(inflight.current(root))


if __name__ == "__main__":
    unittest.main()
