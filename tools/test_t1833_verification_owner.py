"""Real process controls for verification registration and owner-death cleanup."""

from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import suppress
from pathlib import Path
from unittest import mock

from saipen_engine.process_tree import ProcessTree
from saipen_engine.test_runner import TestFamily, _note_spawn_start, _run_family
from saipen_engine import core_unit, verification_cache as cache

TOOLS = Path(__file__).resolve().parent


def wait_for(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError("owned process barrier did not complete")


class LaunchResources(unittest.TestCase):
    def test_interrupted_spawn_stamp_keeps_complete_ownership(self):
        with tempfile.TemporaryDirectory(prefix="t1833-stamp-") as temporary:
            stamp = Path(temporary) / "owner.json"
            stamp.write_text(json.dumps({"pid": os.getpid(), "spawn_phase": "COPYING"}))
            write_text = Path.write_text

            def interrupted_write(path, *args, **kwargs):
                if path == stamp:
                    path.write_bytes(b'{"spawn_')
                    raise KeyboardInterrupt()
                return write_text(path, *args, **kwargs)

            with mock.patch.object(Path, "write_text", interrupted_write), \
                    suppress(KeyboardInterrupt):
                _note_spawn_start(stamp)
            owner = json.loads(stamp.read_text())
            self.assertEqual(owner["pid"], os.getpid())
            self.assertIn(owner["spawn_phase"], {"COPYING", "STARTING"})

    @unittest.skipIf(os.name == "nt", "POSIX descriptor ownership")
    def test_popen_failure_closes_both_guard_pipe_descriptors(self):
        descriptors = []
        pipe = os.pipe

        def observe_pipe():
            pair = pipe()
            descriptors.extend(pair)
            return pair

        with mock.patch("saipen_engine.process_tree.os.pipe", side_effect=observe_pipe), \
                mock.patch("saipen_engine.process_tree.subprocess.Popen",
                           side_effect=OSError("spawn failed")), \
                ProcessTree() as tree, self.assertRaisesRegex(OSError, "spawn failed"):
            tree.start([sys.executable, "-c", "pass"],
                       env={**os.environ, "SAIPEN_CANONICAL_TEST_CHILD": "1"})
        self.assertEqual(len(descriptors), 2)
        for descriptor in descriptors:
            with self.assertRaises(OSError, msg=f"descriptor {descriptor} leaked"):
                os.fstat(descriptor)


@unittest.skipIf(os.name == "nt", "real POSIX process groups and pipe guardian")
class PosixVerificationOwner(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t1833-owner-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.marker = self.root / "verifier.json"

    def env(self):
        return {**os.environ, "SAIPEN_CANONICAL_TEST_CHILD": "1"}

    def test_verifier_cannot_execute_before_reader_registration(self):
        stamp = self.root / "reader.json"
        code = ("import json,os; from pathlib import Path; "
                f"Path({str(self.marker)!r}).write_text(json.dumps("
                f"[os.getpid(),json.loads(Path({str(stamp)!r}).read_text())]))")
        with ProcessTree() as tree:
            def register(process):
                wait_for(tree._guard_info.is_file)
                self.assertFalse(self.marker.exists())
                stamp.write_text(json.dumps(process.pid))

            process = tree.start([sys.executable, "-c", code], env=self.env(),
                                 on_started=register)
            self.assertEqual(process.wait(timeout=10), 0)
            self.assertEqual(json.loads(self.marker.read_text()), [process.pid, process.pid])
            self.assertEqual(tree.pids(), [])

    def test_failed_registration_never_executes_the_verifier(self):
        code = f"from pathlib import Path; Path({str(self.marker)!r}).touch()"
        report = _run_family(self.root, TestFamily("probe", (sys.executable, "-c", code), 10),
                             owner=self.root / "missing-owner.json")
        self.assertEqual(report["status"], "FAIL", report)
        self.assertIn("ownership could not be recorded", report["stderr"])
        self.assertFalse(self.marker.exists())

    def owner_death(self, *, before_registration):
        barrier = self.root / "barrier.json"
        code = ("import os,subprocess,sys,time; from pathlib import Path; "
                "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                f"Path({str(self.marker)!r}).write_text(str(child.pid)); time.sleep(60)")
        owner_code = (
            "import json,sys,time; from pathlib import Path; "
            f"sys.path.insert(0,{str(TOOLS)!r}); "
            "from saipen_engine.process_tree import ProcessTree; "
            "tree=ProcessTree()\n"
            "def register(process):\n"
            f" Path({str(barrier)!r}).write_text(json.dumps(process.pid))\n"
            + (" time.sleep(60)\n" if before_registration else "")
            + f"tree.start([sys.executable,'-c',{code!r}],"
            "env={**__import__('os').environ,'SAIPEN_CANONICAL_TEST_CHILD':'1'},"
            "on_started=register)\ntime.sleep(60)\n"
        )
        owner = subprocess.Popen([sys.executable, "-B", "-c", owner_code],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        foreign = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        group = None
        try:
            wait_for(barrier.is_file)
            group = json.loads(barrier.read_text())
            if not before_registration:
                wait_for(self.marker.is_file)
            owner.kill()
            owner.wait(timeout=10)
            wait_for(lambda: not ProcessTree.group_pids(group))
            self.assertIsNone(foreign.poll(), "guardian killed an unrelated process")
            if before_registration:
                self.assertFalse(self.marker.exists())
            # Recovery can actually launch a fresh verifier after the old group is gone.
            with ProcessTree() as replacement:
                process = replacement.start([sys.executable, "-c", "print('fresh')"],
                                            env=self.env(), stdout=subprocess.PIPE)
                self.assertEqual(process.communicate(timeout=10)[0], b"fresh\n")
                self.assertEqual(process.returncode, 0)
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=10)
            foreign.kill()
            foreign.wait(timeout=10)
            if group is not None:
                with suppress(ProcessLookupError):
                    os.killpg(group, signal.SIGKILL)

    def test_owner_death_before_registration_never_starts_verifier(self):
        self.owner_death(before_registration=True)

    def test_owner_death_reaps_verifier_and_descendants(self):
        self.owner_death(before_registration=False)

    def test_single_flight_recovers_an_actual_orphaned_reader(self):
        identity = {"family": "unit", "fingerprint": "owner-death-control",
                    "verification_identity": {}}
        barrier = self.root / "sandbox.json"
        command = ("import os,time; from pathlib import Path; "
                   f"Path({str(self.marker)!r}).write_text(str(os.getpid())); time.sleep(60)")
        code = (
            "import json,sys; from pathlib import Path; "
            f"sys.path.insert(0,{str(TOOLS)!r}); "
            "from saipen_engine import core_unit,verification_cache as cache; "
            "from saipen_engine.test_runner import TestFamily,_run_family\n"
            f"root=Path({str(self.root)!r})\n"
            f"with cache.single_flight(root,{identity!r}):\n"
            " work=core_unit.new_sandbox_root(root)\n"
            f" Path({str(barrier)!r}).write_text(json.dumps(str(work)))\n"
            f" _run_family(work,TestFamily('probe',(sys.executable,'-c',{command!r}),60),"
            "owner=work/core_unit.SANDBOX_OWNER)\n"
        )
        owner = subprocess.Popen([sys.executable, "-B", "-c", code],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        sandbox = None
        reader = None
        try:
            wait_for(self.marker.is_file)
            reader = int(self.marker.read_text())
            sandbox = Path(json.loads(barrier.read_text()))
            owner.kill()
            owner.wait(timeout=10)
            wait_for(lambda: not ProcessTree.group_pids(reader))
            with self.assertRaisesRegex(ValueError, "without publishing"), \
                    cache.single_flight(self.root, identity, timeout=2), ProcessTree() as tree:
                fresh = tree.start([sys.executable, "-c", "pass"], env=self.env())
                self.assertEqual(fresh.wait(timeout=10), 0)
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=10)
            if reader is not None:
                with suppress(ProcessLookupError):
                    os.killpg(reader, signal.SIGKILL)
            if sandbox is not None:
                core_unit.reclaim(sandbox)

    def test_guardian_holds_neither_output_nor_user_pipe(self):
        reader, writer = os.pipe()
        try:
            with ProcessTree() as tree:
                process = tree.start([sys.executable, "-c", "print('done')"],
                                     env=self.env(), stdout=subprocess.PIPE,
                                     pass_fds=(writer,))
                os.close(writer)
                writer = None
                self.assertEqual(process.communicate(timeout=10)[0], b"done\n")
                self.assertTrue(select.select([reader], [], [], 2)[0],
                                "guardian retained the verifier's user descriptor")
                self.assertEqual(os.read(reader, 1), b"")
        finally:
            os.close(reader)
            if writer is not None:
                os.close(writer)


if __name__ == "__main__":
    unittest.main()
