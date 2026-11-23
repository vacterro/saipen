"""T-1827 / SRC-282: the project writer lock contract, measured.

The external audit (BZDECOMP T-135 / SRC-125) measured four defects:

1. a second writer refused immediately with no holder identity;
2. the pre-BUILD validator capture (240.6 s, 1195 refused acquires) held the
   one writer mutex for minutes;
3. `WriterLock.acquire` was documented as blocking while using `LK_NBLCK`;
4. `saipen/CORE.md` promised a timeout the engine did not have.

Each control here measures a clause of the resulting requirements rather than
re-reading the implementation: bounded acquisition (R001), holder identity in
the refusal (R002), the external capture outside the mutex (R003/R006), the
lock-free status (R004), process-death release with a diagnostic-only holder
record (R005), contract/engine agreement (R007) and the orphan-cleanup remedy
(R010). The two non-goals are pinned too: the lock FILE is permanent (R008) and
a stale capture is retried OUTSIDE the lock, never a longer hold (R009).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from saipen_engine import debt as debt_mod  # noqa: E402
from saipen_engine import intake  # noqa: E402
from saipen_engine import lock as lock_mod  # noqa: E402
from saipen_engine import release as release_mod  # noqa: E402
from saipen_engine.lock import (  # noqa: E402
    WriterBusy,
    WriterLock,
    lock_status,
    project_writer_lock,
    writer_busy_payload,
)

SCENARIO = ROOT / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"
CLI = TOOLS / "saipen.py"

_HOLDER_SCRIPT = """
import sys, time
sys.path.insert(0, {tools!r})
from pathlib import Path
from saipen_engine.lock import WriterLock
lock = WriterLock(Path({root!r}))
lock.acquire()
print("HELD", flush=True)
sys.stdin.readline()
lock.release()
"""

_WAIT_THEN_HOLD_SCRIPT = """
import sys
sys.path.insert(0, {tools!r})
from pathlib import Path
from saipen_engine.lock import WriterLock
print("READY", flush=True)
sys.stdin.readline()
lock = WriterLock(Path({root!r}))
lock.acquire()
print("HELD", flush=True)
sys.stdin.readline()
lock.release()
"""


def _send(process: subprocess.Popen, line: str = "\n") -> None:
    """Write one line to a holder child and FLUSH it (a buffered pipe does not
    deliver on write alone)."""
    process.stdin.write(line)
    process.stdin.flush()


def _canned(problems=None) -> dict:
    problems = list(problems or [])
    return {
        "ok": True,
        "exit_code": 0 if not problems else 1,
        "gate": "core",
        "problems": problems,
        "warnings": [],
    }


class _SyncProject(unittest.TestCase):
    """A minimal real project: canonical STATE/BOARD/LOG under .saipen."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1827-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")

    def tearDown(self) -> None:
        # Stop every holder we started BEFORE removing the tree: a live child
        # holding core.lock keeps the file open on Windows and the cleanup
        # would fail on a file the test itself is responsible for.
        for process in getattr(self, "_holders", []):
            if process.poll() is None:
                process.kill()
            process.wait(10)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
        self.tmp.cleanup()

    def _holder_process(self, script: str = _HOLDER_SCRIPT, ready: str = "HELD"):
        path = script.format(tools=str(TOOLS), root=str(self.root))
        process = subprocess.Popen(
            [sys.executable, "-c", path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        holders = getattr(self, "_holders", None)
        if holders is None:
            holders = self._holders = []
        holders.append(process)
        lines = []
        while True:
            line = process.stdout.readline().strip()
            if not line:
                self.fail("holder process died: " + process.stderr.read())
            lines.append(line)
            if line == ready:
                break
        # The child writes its holder record after acquiring; give the write a
        # moment to land so an identity assertion is not a scheduling race.
        deadline = time.monotonic() + 5
        record = self.root / ".saipen/locks/core.lock.holder"
        while not record.is_file() and time.monotonic() < deadline:
            time.sleep(0.02)
        return process


class BoundedAcquisitionTests(_SyncProject):
    """R001: a short holder is waited for; a long one is refused in bounded time."""

    def test_a_short_hold_is_waited_out_and_acquired(self) -> None:
        process = self._holder_process()
        threading.Timer(0.6, _send, args=(process,)).start()
        started = time.monotonic()
        acquired = WriterLock(self.root, timeout=5.0)
        self.assertTrue(acquired.acquire(), "a short legitimate hold must be waited for")
        elapsed = time.monotonic() - started
        acquired.release()
        self.assertGreaterEqual(elapsed, 0.4, elapsed)
        self.assertLess(elapsed, 5.0, elapsed)

    def test_an_unbounded_holder_is_refused_within_the_declared_budget(self) -> None:
        process = self._holder_process()
        try:
            with patch.dict(os.environ, {"SAIPEN_WRITER_LOCK_TIMEOUT": "0.3"}):
                started = time.monotonic()
                with self.assertRaises(WriterBusy) as caught:
                    project_writer_lock(self.root).__enter__()
                elapsed = time.monotonic() - started
            self.assertEqual(str(caught.exception), "WRITER_BUSY")
            self.assertGreaterEqual(elapsed, 0.2, elapsed)
            self.assertLess(elapsed, 3.0, elapsed)
        finally:
            _send(process)

    def test_a_long_external_capture_does_not_block_a_short_mutation(self) -> None:
        """R001/R003/R006: the measured 240 s hold was the capture, and the
        capture now runs outside the mutex. A mutation arriving mid-capture
        acquires the lock at once instead of waiting for the capture."""
        capture_entered = threading.Event()
        release_capture = threading.Event()

        def slow_capture(root, *, gate="core"):
            capture_entered.set()
            release_capture.wait(30)
            return _canned()

        result: dict = {}

        def baseline() -> None:
            result["value"] = debt_mod.create_snapshot(
                self.root, "probe", "pre-BUILD baseline probe"
            )

        with patch.object(debt_mod, "capture_findings", side_effect=slow_capture):
            worker = threading.Thread(target=baseline)
            worker.start()
            self.assertTrue(capture_entered.wait(10), "the capture never started")
            # The capture is in flight; the writer mutex must be FREE.
            self.assertFalse(lock_status(self.root)["held"])
            started = time.monotonic()
            budget = patch.dict(os.environ, {"SAIPEN_WRITER_LOCK_TIMEOUT": "1.0"})
            with budget, project_writer_lock(self.root):
                pass
            self.assertLess(time.monotonic() - started, 1.0)
            release_capture.set()
            worker.join(30)
            self.assertFalse(worker.is_alive())
        self.assertTrue(result["value"]["ok"], result["value"])

    def test_a_capture_overtaken_by_a_mutation_is_retried_outside_the_lock(self) -> None:
        """R009: the remedy is a fresh capture outside the mutex, never a retry
        while holding it. The recorded checkpoint must be the new one."""
        attempts: list[int] = []
        mutated = threading.Event()

        def capture_during_a_mutation(root, *, gate="core"):
            attempts.append(1)
            if not mutated.is_set():
                intake.capture(self.root, "concurrent write", source_kind="user_audit")
                mutated.set()
            return _canned()

        with patch.object(debt_mod, "capture_findings", side_effect=capture_during_a_mutation):
            result = debt_mod.create_snapshot(self.root, "probe", "stale capture probe")
        self.assertTrue(result["ok"], result)
        self.assertGreaterEqual(len(attempts), 2, "the stale capture was not retried")
        record = debt_mod.load_snapshot(self.root, result["snapshot_id"])
        live_board = (self.root / ".saipen/BOARD.md").read_bytes()
        import hashlib

        # Recorded checkpoints carry the bounded quick-hash form.
        self.assertTrue(
            hashlib.sha256(live_board).hexdigest().startswith(record["board_sha256"]),
            (record["board_sha256"], hashlib.sha256(live_board).hexdigest()),
        )


class HolderIdentityTests(_SyncProject):
    """R002: the refusal names the holder, or states plainly that it is unknown."""

    def test_a_saipen_holder_is_named_by_pid_and_command(self) -> None:
        process = self._holder_process()
        try:
            budget = patch.dict(os.environ, {"SAIPEN_WRITER_LOCK_TIMEOUT": "0.2"})
            with budget, self.assertRaises(WriterBusy) as caught:
                project_writer_lock(self.root).__enter__()
            payload = writer_busy_payload(caught.exception)
            self.assertEqual(payload["code"], "WRITER_BUSY")
            self.assertEqual(payload["holder"]["pid"], process.pid, payload)
            self.assertIn(f"pid {process.pid}", payload["detail"])
            self.assertIn("running `", payload["detail"])
        finally:
            process.stdin.close()
            process.wait(10)

    def test_an_unreadable_holder_record_says_the_holder_is_unknown(self) -> None:
        process = self._holder_process()
        (self.root / ".saipen/locks/core.lock.holder").unlink()
        try:
            budget = patch.dict(os.environ, {"SAIPEN_WRITER_LOCK_TIMEOUT": "0.2"})
            with budget, self.assertRaises(WriterBusy) as caught:
                project_writer_lock(self.root).__enter__()
            payload = writer_busy_payload(caught.exception)
            self.assertNotIn("holder", payload)
            self.assertIn("holder is unknown", payload["detail"])
        finally:
            process.stdin.close()
            process.wait(10)

    def test_the_status_projection_names_the_live_holder(self) -> None:
        process = self._holder_process()
        try:
            payload = lock_status(self.root)
            self.assertTrue(payload["held"], payload)
            self.assertEqual(payload["state"], "held")
            self.assertEqual(payload["holder"]["pid"], process.pid)
            self.assertIn(str(process.pid), payload["detail"])
        finally:
            process.stdin.close()
            process.wait(10)


class ProcessDeathAndRecordTests(_SyncProject):
    """R005/R008: the OS lock dies with its holder; the record never gates."""

    def test_process_death_releases_the_lock(self) -> None:
        process = self._holder_process()
        process.kill()
        process.wait(10)
        started = time.monotonic()
        with project_writer_lock(self.root):
            pass
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(lock_status(self.root)["state"], "free")

    def test_a_stale_holder_record_never_blocks_acquisition(self) -> None:
        record = self.root / ".saipen/locks/core.lock.holder"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(
            json.dumps({"schema": 1, "pid": 999_999, "acquired_at": "2000-01-01T00:00:00Z",
                        "command": "dead.py"}),
            encoding="utf-8",
        )
        with project_writer_lock(self.root):
            pass
        self.assertEqual(lock_status(self.root)["state"], "free")

    def test_the_holder_record_is_withdrawn_on_release(self) -> None:
        """R005: no holder record may outlive its holder.

        A record left behind by a free lock is not just noise -- it lets a
        later refusal name a process that no longer holds anything, and it
        changes project bytes after the operation that wrote them finished.
        """
        record = self.root / ".saipen/locks/core.lock.holder"
        with project_writer_lock(self.root):
            self.assertTrue(record.is_file(), "a held lock must publish its holder")
        self.assertFalse(record.is_file(), "a released lock must withdraw its record")
        self.assertEqual(lock_status(self.root)["state"], "free")
        self.assertIsNone(lock_status(self.root)["last_holder"])

    def test_a_record_rewritten_by_a_successor_is_not_withdrawn(self) -> None:
        """Only the releaser's own bytes are removed, never a successor's."""
        record_path = self.root / ".saipen/locks/core.lock.holder"
        lock = WriterLock(self.root)
        lock.acquire()
        successor = {"schema": 1, "pid": 424_242, "acquired_at": "2030-01-01T00:00:00Z",
                     "command": "successor.py"}
        record_path.write_text(json.dumps(successor), encoding="utf-8")
        lock.release()
        self.assertTrue(record_path.is_file(), "a successor's record was deleted")
        self.assertEqual(json.loads(record_path.read_text(encoding="utf-8"))["pid"], 424_242)

    def test_the_lock_file_stays_a_permanent_zero_byte_carrier(self) -> None:
        """R008: never delete the lock file to cure a hold."""
        with project_writer_lock(self.root):
            pass
        path = self.root / ".saipen/locks/core.lock"
        self.assertTrue(path.is_file())
        self.assertEqual(path.stat().st_size, 0)
        with project_writer_lock(self.root):
            pass
        self.assertTrue(path.is_file())
        self.assertEqual(path.stat().st_size, 0)


class StatusAndYieldTests(_SyncProject):
    """R003/R004: status answers under a hold; a yielded lock re-proves."""

    def test_lock_status_never_acquires_the_lock(self) -> None:
        with project_writer_lock(self.root):
            self.assertTrue(lock_status(self.root)["held"])
        self.assertEqual(lock_status(self.root)["state"], "free")

    def test_saipen_status_answers_while_another_writer_holds_the_lock(self) -> None:
        process = self._holder_process()
        try:
            env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
            run = subprocess.run(
                [sys.executable, str(CLI), "status", "--json"],
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=120,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertTrue(json.loads(run.stdout)["ok"], run.stdout)
        finally:
            process.stdin.close()
            process.wait(10)

    def test_a_yielded_lock_is_retaken_and_a_lost_race_refuses(self) -> None:
        process = self._holder_process(_WAIT_THEN_HOLD_SCRIPT, ready="READY")
        try:
            with project_writer_lock(self.root) as lock:
                with lock_mod.writer_lock_yielded(lock):
                    # Another PROCESS takes the mutex in the window: the
                    # re-acquisition must refuse instead of writing unlocked.
                    _send(process)
                    self.assertEqual(process.stdout.readline().strip(), "HELD")
                self.fail("a lost re-acquisition must raise WriterBusy")
        except WriterBusy:
            pass
        finally:
            _send(process)


class ContractAgreementTests(_SyncProject):
    """R007/R010: engine docstring and CORE.md state the same bounded contract."""

    def test_acquire_docstring_states_the_bounded_wait(self) -> None:
        doc = WriterLock.acquire.__doc__ or ""
        self.assertIn("bounded wait", doc)
        self.assertIn("SAIPEN_WRITER_LOCK_TIMEOUT", doc)
        self.assertIn("WRITER_BUSY", doc)

    def test_core_contract_states_the_budget_override_and_refusal(self) -> None:
        text = (ROOT / "saipen" / "CORE.md").read_text(encoding="utf-8")
        self.assertIn("SAIPEN_WRITER_LOCK_TIMEOUT", text)
        self.assertIn("WRITER_BUSY", text)
        self.assertIn("saipen lock", text)
        self.assertIn("holder", text)

    def test_the_remediation_names_the_orphan_procedure_not_file_deletion(self) -> None:
        payload = writer_busy_payload(WriterBusy("busy"))
        remedy = payload["remediation"]
        self.assertIn("saipen lock status", remedy)
        self.assertIn("recorded", remedy)
        self.assertIn("Never delete .saipen/locks/core.lock", remedy)


class ReleaseGateWindowTests(unittest.TestCase):
    """R003: the release gate runs with the writer mutex RELEASED."""

    def test_the_ship_gate_runs_outside_the_writer_lock(self) -> None:
        try:
            from test_t1746_crew_terminal_outcome import _DownstreamShape
        except ImportError:  # pragma: no cover - discovery always has the suite
            self.skipTest("release fixture unavailable")

        fixture = _DownstreamShape()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        # T-1890: `plan_release` refuses a project with no VERSION, and the crew
        # carrier refuses one with no owning ticket. Without both, this test died
        # inside `plan_release` and never reached the gate, so the invariant it
        # exists to measure was never measured. `wide=False` matches the digests
        # the planner re-derives from the deferred scope.
        fixture._shape(version="8.0.1", ticket="T-11", wide=False)
        plan = fixture._plan()
        seen: list[dict] = []

        def gate(root, name):
            seen.append(lock_status(root))
            return {"ok": True}

        ready, _gate, parity = fixture._patches()
        with ready, parity, patch.object(release_mod, "_run_gate", side_effect=gate):
            result = release_mod.execute_release(fixture.root, plan)
        self.assertTrue(result["ok"], result)
        self.assertTrue(seen, "the gate never ran")
        self.assertFalse(seen[0]["held"], f"the writer lock was held for the gate: {seen[0]}")
        self.assertEqual(lock_status(fixture.root)["state"], "free")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
