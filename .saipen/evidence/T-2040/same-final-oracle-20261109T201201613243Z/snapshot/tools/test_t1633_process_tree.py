"""T-1633: smoke timeouts own the host tree; family records carry orphan PIDs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import test_opencode_host_smoke as smoke
from saipen_engine import core_unit
from saipen_engine.test_runner import TestFamily


class ProcessOwnership(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="t1633-owned-")
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.pid_file = self.root / "host.pid"
        self.host_pid = None

    def cleanup_host(self):
        if self.pid_file.is_file():
            self.host_pid = int(self.pid_file.read_text())
        if self.host_pid and core_unit.pid_alive(self.host_pid):
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/PID", str(self.host_pid)],
                               stdin=subprocess.DEVNULL, capture_output=True, check=False)
            else:
                os.kill(self.host_pid, 9)

    def shim(self, *, exits=False, inherited=True):
        child = ("import os,time; from pathlib import Path; "
                 f"Path({str(self.pid_file)!r}).write_text(str(os.getpid())); time.sleep(15)")
        output = "" if inherited else ", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL"
        launcher = (
            "import subprocess,sys,time; from pathlib import Path; "
            f"subprocess.Popen([sys.executable,'-c',{child!r}], stdin=subprocess.DEVNULL{output}); "
            f"marker=Path({str(self.pid_file)!r}); "
            "\nwhile not marker.exists(): time.sleep(.01)\n"
            + ("" if exits else "time.sleep(60)\n")
        )
        self.addCleanup(self.cleanup_host)
        return [sys.executable, "-c", launcher]

    def assert_host_gone(self):
        self.assertTrue(self.pid_file.is_file(), "stand-in host never started")
        self.host_pid = int(self.pid_file.read_text())
        deadline = time.monotonic() + 3
        while core_unit.pid_alive(self.host_pid) and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertFalse(core_unit.pid_alive(self.host_pid), "host outlived its smoke launcher")

    def test_timeout_reaps_host_and_keeps_an_unrelated_process_alive(self):
        foreign = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        try:
            launcher = getattr(smoke, "run_host", subprocess.run)
            with self.assertRaises(subprocess.TimeoutExpired):
                launcher(self.shim(inherited=False), capture_output=True, timeout=2)
            self.assert_host_gone()
            self.assertIsNone(foreign.poll())
        finally:
            foreign.kill()
            foreign.wait(timeout=10)

    def test_timeout_reaps_a_host_even_after_its_shim_has_exited(self):
        launcher = getattr(smoke, "run_host", subprocess.run)
        began = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            launcher(self.shim(exits=True), capture_output=True, timeout=2)
        self.assertLess(time.monotonic() - began, 8, "timeout waited for the orphan to exit")
        self.assert_host_gone()

    def test_successful_shim_cannot_leave_a_detached_host(self):
        launcher = getattr(smoke, "run_host", subprocess.run)
        completed = launcher(self.shim(exits=True, inherited=False),
                             capture_output=True, timeout=10)
        self.assertEqual(completed.returncode, 0)
        self.assert_host_gone()

    def test_regular_output_and_check_contract_are_preserved(self):
        launcher = getattr(smoke, "run_host", subprocess.run)
        result = launcher([sys.executable, "-c", "print('ordinary')"],
                          capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(result.stdout.strip(), "ordinary")
        binary = launcher([sys.executable, "-c", "print('binary')"],
                          capture_output=True, timeout=10, check=True)
        self.assertEqual(binary.stdout.strip(), b"binary")
        with self.assertRaises(subprocess.CalledProcessError) as refused:
            launcher([sys.executable, "-c", "import sys; sys.exit(3)"],
                     capture_output=True, timeout=10, check=True)
        self.assertEqual(refused.exception.returncode, 3)

    def test_core_family_reports_and_reaps_a_shards_lingering_host(self):
        subject = self.root / "subject"
        subject.mkdir()
        command = self.shim(exits=True, inherited=False)
        # A real family root exits green after spawning the lingering host.
        command[-1] += ("\nprint('Ran 1 test in 0.01s', file=sys.stderr); "
                        "print('OK', file=sys.stderr)\n")
        family = TestFamily(core_unit.FAMILY_NAME, tuple(command), 30)
        with mock.patch.object(core_unit, "family", return_value=family):
            run = core_unit.run_family(subject)
        self.assert_host_gone()
        self.assertIn(self.host_pid, run.get("processes_leaked", []), run)
        self.assertEqual(run["ran"], 1)
        self.assertEqual(run["status"], "PASS")

    def test_a_record_preserves_the_reported_process_ids(self):
        root = self.root / "record"
        root.mkdir()
        (root / "tools").mkdir()
        baseline = Path(__file__).parent / "core_unit_baseline.json"
        (root / core_unit.BASELINE_REL).write_bytes(baseline.read_bytes())
        run = {"status": "PASS", "exit_code": 0, "ran": 1, "red": [],
               "command": ["python", "-m", "unittest"], "duration_s": .01,
               "tallied": 1, "unparsed": 0, "processes_leaked": [12345]}
        written = core_unit.write_record(root, run, "1633" * 4)
        record = json.loads((root / written["path"]).read_text())
        self.assertEqual(record.get("processes_leaked"), [12345])


if __name__ == "__main__":
    unittest.main()
