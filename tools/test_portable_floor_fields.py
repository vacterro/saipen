"""Portable dependency checks consume structured fields; parity uses the native floor."""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_floor
import audit_parity
from saipen_engine.board import parse_board
from saipen_engine.process_tree import ProcessTree

ROOT = Path(__file__).resolve().parents[1]


class PortableNeedsFields(unittest.TestCase):
    #: T-2163 (Campaign XII P1-B), measured 2026-11-22 on this host under
    #: family-representative ambient load: the MSYS bash floor outlived a
    #: fixed 30 s window in 7 of 10 samples (p50 30.7 s, p95 330 s -- the
    #: kill was held hostage by pipe-holding grandchildren a bare kill
    #: could not reach), while the PowerShell floor kept >= 1.2x headroom
    #: across all 16 samples.
    #:
    #: Campaign XIII tightened that contract twice (P0-A/P0-B):
    #:
    #: 1. P0-B -- the floor child runs inside an OWNED process tree
    #:    (session/group leader on POSIX via start_new_session, an assigned
    #:    Job Object on Windows), so a window expiry ends the whole tree:
    #:    grandchildren cannot outlive the kill, hold the output pipes, and
    #:    stall communicate() past the declared window. The old path
    #:    (plain Popen + killpg fallback) killed only the direct child on
    #:    POSIX and left the wall to the grandchildren's lifetime. The owned
    #:    kill is SIGKILL/TerminateJobObject with no TERM phase: a stalled
    #:    floor gets no cleanup time it already failed to use, and SIGKILL
    #:    is the one signal a hung child cannot ignore (the bounded
    #:    escalation question answered by design, not by timeout ladder).
    #: 2. P0-A -- a window expiry is an unfinished measurement, never a
    #:    verdict: the runner is remeasured once at double the window; a
    #:    runner that answers is judged only on that answer (known-bad
    #:    stays red fast); a runner that answers in NEITHER window is
    #:    INCONCLUSIVE_TIMEOUT, and no governing contract lets an
    #:    inconclusive floor stand for a verified one, so the field fails
    #:    closed instead of skipping. The named measurement skip this
    #:    path used to take is exactly how a mandatory floor silently
    #:    stopped being verified, and this class refuses to rent it again.
    FLOOR_WINDOW_S = 30.0
    #: The documented, bounded reap allowance (P0-B acceptance): after the
    #: owned tree is terminated the second communicate() is bounded by this,
    #: so the wall of an expired window stays at window + allowance even
    #: when grandchildren held both pipes.
    FLOOR_CLEANUP_ALLOWANCE_S = 10.0

    #: P0-A verdict classes. A floor either answers -- VERIFIED_PASS or
    #: VERIFIED_FAIL, judged strictly on that answer -- or it does not:
    #: UNAVAILABLE_PLATFORM names a floor whose absence the host contract
    #: allows (never the native one), and INCONCLUSIVE_TIMEOUT names an
    #: available floor that never answered, which fails closed.
    VERIFIED_PASS = "VERIFIED_PASS"
    VERIFIED_FAIL = "VERIFIED_FAIL"
    UNAVAILABLE_PLATFORM = "UNAVAILABLE_PLATFORM"
    INCONCLUSIVE_TIMEOUT = "INCONCLUSIVE_TIMEOUT"

    def mandatory_floor_labels(self) -> tuple[str, ...]:
        """The floor that is mandatory release coverage on this host.

        ``audit_parity`` measures the native surface -- PowerShell on win32,
        bash on POSIX -- and this is the same per-platform mapping the field
        tests treat as mandatory: a missing native floor may not be
        substituted by an optional one. The other floor, when installed, is
        optional cross-platform corroboration: audit_parity documents the
        loud POSIX-shell skip for the parity diagnostic, and this harness
        honors that absence by simply not running it -- but an AVAILABLE
        floor is never allowed to time out into silence.
        """
        if os.name == "nt":
            return ("ps1",)
        return ("sh",)

    def floor_runners(self) -> list:
        runners = []
        bash = audit_floor.find_bash()
        pwsh = audit_floor.find_pwsh()
        if bash:
            runners.append((
                "sh", [bash, str(ROOT / "tests/validate.sh")], audit_floor.bash_env(bash),
            ))
        if pwsh:
            runners.append((
                "ps1", [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(ROOT / "tests/validate.ps1")], os.environ.copy(),
            ))
        labels = [label for label, _command, _environment in runners]
        mandatory = self.mandatory_floor_labels()
        if not any(label in mandatory for label in labels):
            self.fail(
                f"the mandatory portable floor for this host is "
                f"{self.UNAVAILABLE_PLATFORM}: the release coverage floor "
                f"{mandatory[0]!r} is not installed, and the optional floors "
                f"in the set {labels or ['none']} cannot substitute for it"
            )
        return runners

    def run_floor_once(self, command, cwd, environment, window):
        """One floor invocation inside an owned, bounded process tree.

        The child is started through ``ProcessTree``: session leader on
        POSIX, an assigned Job Object on Windows. On window expiry the owned
        tree is terminated and the reap is bounded by
        FLOOR_CLEANUP_ALLOWANCE_S -- the kill reaches the pipe holders, so
        communicate() cannot stay hostage to a grandchild's lifetime past
        window + allowance.
        """
        started = time.monotonic()
        stdout = ""
        stderr = ""
        with ProcessTree() as tree:
            process = tree.start(
                command, cwd=cwd, env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=window)
            except subprocess.TimeoutExpired:
                tree.terminate()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    stdout, stderr = process.communicate(
                        timeout=self.FLOOR_CLEANUP_ALLOWANCE_S
                    )
                # An answer that arrives while a murdered tree is reaped
                # belongs to a killed child and cannot speak for the subject.
                return None, time.monotonic() - started, stdout + stderr
        wall = time.monotonic() - started
        if wall >= window:
            # Answered at the window edge: the expiry owns this wall, and
            # the race-not the runner-decides nothing about the subject.
            return None, wall, stdout + stderr
        return process.returncode, None, stdout + stderr

    def run_floor(self, label, command, cwd, environment):
        """The runner's verdict class, or the composed fail-closed refusal.

        Remeasured once at double the window (the measured p50 sat on the
        window's edge, not on the floor's opinion). A runner that answers
        inside a window is judged only on that answer; a runner that answers
        in neither window is INCONCLUSIVE_TIMEOUT, and the caller fails
        closed on that verdict -- never skips it.
        """
        windows = (self.FLOOR_WINDOW_S, self.FLOOR_WINDOW_S * 2)
        walls: list[float] = []
        for window in windows:
            returncode, wall, output = self.run_floor_once(
                command, cwd, environment, window
            )
            walls.append(wall)
            if returncode is not None:
                return {
                    "verdict": (
                        self.VERIFIED_PASS
                        if returncode == 0
                        else self.VERIFIED_FAIL
                    ),
                    "returncode": returncode,
                    "output": output,
                    "walls": walls,
                }
        bounds = ", ".join(f"{value:.1f} s" for value in walls)
        return {
            "verdict": self.INCONCLUSIVE_TIMEOUT,
            "returncode": None,
            "output": (
                f"floor {label} is {self.INCONCLUSIVE_TIMEOUT}: the platform "
                f"is available but the runner answered inside neither window "
                f"({windows[0]:.0f} s then {windows[1]:.0f} s; measured "
                f"walls {bounds}); an unanswered floor is not a verified "
                f"floor -- it fails closed, it does not skip"
            ),
            "walls": walls,
        }

    def run_floors(self, board: str, *, valid: bool, diagnostic: str = "") -> None:
        parsed = parse_board(board)
        self.assertEqual(parsed.get("errors"), [], parsed)
        with tempfile.TemporaryDirectory(prefix="saipen-floor-field-") as tmp:
            fixture = Path(tmp)
            memory = fixture / ".saipen"
            memory.mkdir()
            for name, text in (
                ("STATE.md", audit_floor.GOOD_STATE),
                ("BOARD.md", board), ("LOG.md", audit_floor.GOOD_LOG),
            ):
                (memory / name).write_text(text, encoding="utf-8")
            for label, command, environment in self.floor_runners():
                with self.subTest(floor=label):
                    before = {p.name: p.read_bytes() for p in memory.iterdir()}
                    verdict = self.run_floor(label, command, fixture, environment)
                    #: A timeout (or its kill) must not corrupt the evidence
                    #: either (P0-A mandated controls): the bytes are
                    #: compared BEFORE the verdict is judged, so a murdered
                    #: floor that tore the fixture is named for the
                    #: corruption, and a clean inconclusive floor reaches
                    #: its fail-closed refusal only on provably intact bytes.
                    self.assertEqual(
                        {p.name: p.read_bytes() for p in memory.iterdir()},
                        before,
                        "the floor changed the tested memory",
                    )
                    if verdict["verdict"] == self.INCONCLUSIVE_TIMEOUT:
                        self.fail(verdict["output"])
                    if valid:
                        self.assertEqual(
                            verdict["verdict"], self.VERIFIED_PASS, verdict["output"]
                        )
                    else:
                        self.assertEqual(
                            verdict["verdict"], self.VERIFIED_FAIL, verdict["output"]
                        )
                        self.assertIn(diagnostic, verdict["output"])

    def test_description_and_blocker_prose_do_not_create_dependencies(self) -> None:
        board = """# Board
## DOING
## TODO
- [ ] T-001 Documentation example needs: T-999 | verify: prose is opaque
- [ ] T-002 Actual dependency | needs: T-001 | verify: dependency resolves
## DONE
## BLOCKED
- [ ] T-003 Parked work | blocker: narrative mentions needs: T-999 and needs: external service
"""
        self.run_floors(board, valid=True)

    def test_narrative_self_reference_does_not_create_a_cycle(self) -> None:
        board = audit_floor.GOOD_BOARD.replace("a ticket", "Example needs: T-001")
        self.run_floors(board, valid=True)

    def test_real_dangling_field_still_fails(self) -> None:
        board = audit_floor.GOOD_BOARD.replace("a ticket", "a ticket | needs: T-999")
        self.run_floors(board, valid=False, diagnostic="dangling needs:")

    def test_real_cycle_still_fails(self) -> None:
        board = audit_floor.GOOD_BOARD.replace("a ticket", "a ticket | needs: T-002")
        board = board.replace("## DONE", "- [ ] T-002 second | needs: T-001\n## DONE")
        self.run_floors(board, valid=False, diagnostic="cyclic needs:")


class NativeParityTransport(unittest.TestCase):
    def probe(self, name: str, platform: str, *, validator_return: int,
              floor_return: int) -> tuple[list[list[str]], str]:
        with tempfile.TemporaryDirectory(prefix="saipen-parity-native-") as tmp:
            home = Path(tmp) / "home"
            (home / "tools").mkdir(parents=True)
            (home / "tools/audit_checks.py").write_text("IGNORE = None\n", encoding="utf-8")
            fake_os = types.SimpleNamespace(name=name, path=os.path, environ={})
            fake_sys = types.SimpleNamespace(platform=platform, executable=sys.executable,
                                             modules=sys.modules)
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                result = validator_return if command[0] == sys.executable else floor_return
                return subprocess.CompletedProcess(
                    command, result, stdout="FAIL: deliberate control\n", stderr="",
                )

            output = io.StringIO()
            previous = sys.modules.get("audit_checks")
            try:
                with patch.object(audit_parity, "HOME", home), \
                        patch.object(audit_parity, "os", fake_os), \
                        patch.object(audit_parity, "sys", fake_sys), \
                        patch.object(audit_parity, "find_bash", return_value="test-bash"), \
                        patch.object(audit_parity, "bash_env", return_value={}), \
                        patch.object(audit_parity.subprocess, "run", side_effect=run), \
                        contextlib.redirect_stdout(output):
                    self.assertEqual(audit_parity.main(), 1, "known-bad preflight passed")
            finally:
                if previous is None:
                    sys.modules.pop("audit_checks", None)
                else:
                    sys.modules["audit_checks"] = previous
            return calls, output.getvalue()

    def test_win32_runtime_uses_powershell_without_changing_the_timeout(self) -> None:
        calls, _output = self.probe("nt", "win32", validator_return=1, floor_return=0)
        self.assertEqual(calls[1][0], "powershell.exe")
        self.assertIn("tests/validate.ps1", calls[1])
        self.assertEqual(audit_parity.VALIDATOR_TIMEOUT, 60)
        self.assertEqual(audit_parity.BASELINE, 11)

    def test_posix_runtime_keeps_the_bash_floor(self) -> None:
        calls, _output = self.probe("posix", "linux", validator_return=1, floor_return=0)
        self.assertEqual(calls[1], ["test-bash", "tests/validate.sh"])

    def test_native_floor_failure_names_the_runner_that_failed(self) -> None:
        _calls, output = self.probe("nt", "win32", validator_return=0, floor_return=1)
        self.assertIn("tests/validate.ps1 rejects an UNMODIFIED copy", output)


if __name__ == "__main__":
    unittest.main()
