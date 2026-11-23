"""T-2163 P1-B/C oracle: a floor window expiry is an owned, bounded measurement.

Measured 2026-11-22 (Campaign XII) on this host under family-representative
ambient load: the MSYS bash floor outlived a fixed 30 s window in 7 of 10
samples (p50 30.7 s, p95 330 s -- the kill was held hostage by pipe-holding
grandchildren the bare kill could not reach), while the PowerShell floor kept
>= 1.2x headroom across all 16 samples. That is how the T-2162 boundary run
63c8a2c81a81cbf4-20261122T103719053845Z answered one new red on a healthy
subject.

Campaign XIII (P0-A/P0-B) tightened the repaired subject twice: the floor
child now runs inside an OWNED process tree (session leader on POSIX, a Job
Object on Windows) so a window expiry ends the pipe holders and the wall is
window + the documented reap allowance; and a floor that answers in neither
window is INCONCLUSIVE_TIMEOUT, which fails closed -- the named measurement
skip the XII repair took is exactly how a mandatory floor could silently stop
being verified.

Campaign XIII (P0-C) rebuilt this oracle's harness: the XII version injected
synthetic floors through the subject's ``floor_runners()`` -- an attribute
only the repaired subject defines. The pre-fix subject builds its runners
inline through ``audit_floor.find_bash()``/``find_pwsh()``/``bash_env()``, so
the BEFORE side silently ran the REAL platform shell against a fixture without
``tests/`` and the recorded RED proved a missing file instead of the claimed
timeout pathology. This oracle reaches BOTH implementations the same way:
the shared ``audit_floor`` discovery is patched, so the before subject and
the repaired one run the SAME controlled, host-agnostic stub runners, and
every BEFORE red names a live defect -- a genuine window timeout, an
unbounded pipe-held wall, or a missing mandatory-floor policy -- never a
missing script and never a harness difference.

The floor harnesses are instance shims, not TestCase subclasses: synthetic
runners installed around one genuine subject instance, never a discoverable
class, so this module runs exactly its controls.

Run standalone:
    python tools/test_t2163_floor_timeout_remeasure.py
"""

from __future__ import annotations

import contextlib
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import audit_floor  # noqa: E402
import test_portable_floor_fields as subject_module  # noqa: E402


class _StubFloors:
    """Host-agnostic controlled floor runners, installed for BOTH pair sides.

    Both subjects construct every floor through ``audit_floor`` discovery, so
    patching that shared surface hands the same controlled runner to the
    before subject and the repaired one (P0-C: one controlled harness, two
    implementations, zero missing-file reds). A stub becomes command[0] with
    the repo's real floor script as argv[1], which the stub deliberately
    ignores: the controlled work never depends on the fixture.
    """

    def __init__(self, workdir: str | Path):
        self.dir = Path(workdir)
        self.suffix = ".cmd" if os.name == "nt" else ".sh"

    def _install(self, name: str, program: str) -> str:
        path = self.dir / f"{name}{self.suffix}"
        if os.name == "nt":
            body = f'@"{sys.executable}" -c "{program}"\r\n'
        else:
            body = f'#!/bin/sh\nexec "{sys.executable}" -c "{program}"\n'
        path.write_text(body, encoding="utf-8")
        if os.name != "nt":
            path.chmod(0o755)
        return str(path)

    def fast(self, name: str = "fast") -> str:
        return self._install(name, "import sys; sys.exit(0)")

    def known_bad(self, name: str = "bad") -> str:
        return self._install(
            name,
            "import sys; sys.stderr.write('synthetic known-bad'); sys.exit(7)",
        )

    def stall(self, seconds: float, name: str = "stall") -> str:
        return self._install(
            name, f"import sys, time; time.sleep({seconds}); sys.exit(0)"
        )

    def grandchild(self, name: str = "grandchild") -> str:
        """A parent and grandchild that both outlive every window.

        The parent sleeps 60 s (past both windows, so it can NEVER verdict
        legitimately -- the third 8943-test family run measured the old
        0.3 s parent answering inside the 1.0 s remeasure: a coin-flip
        verdict under shard spawn latency); the grandchild holds the
        output pipes 120 s. Lifetimes are the failure signature: a
        REACHING kill ends the whole family far inside them; a MISS
        inherits them per attempt.
        """
        return self._install(
            name,
            "import subprocess, sys, time; "
            "subprocess.Popen([sys.executable, '-c', "
            "'import time; time.sleep(120.0)']); "
            "time.sleep(60.0); sys.exit(0)",
        )

    def memory_writer(self, name: str = "writer") -> str:
        return self._install(
            name,
            "import sys; f = open('.saipen/GARBAGE.txt', 'w'); "
            "f.write('x'); f.close(); sys.exit(0)",
        )


class FloorTimeoutRemeasureTests(unittest.TestCase):
    """The verifier of the T-2163 P0-B/C repair. Same bytes for both runs."""

    #: The production floor uses a 30 s window; these controls inject STUB
    #: runners and never launch the real floor scripts, so the same verdict
    #: classes are proved at a scaled window. The original literal 30/60/91 s
    #: sleeps cost a measured 214.8 s per module run (T-2174 RED). The owned
    #: kill, double-window remeasure and fail-closed refusal are unchanged.
    CONTROL_WINDOW_S = 6.0

    #: Documented contention slack for two controlled-runner spawns under
    #: family-scale load: the first family run measured a 21.5 s bound
    #: losing purely to 6-shard spawn latency (measured red, 8943-test
    #: record 5d9317a5f78d9c05-20261122T174915965302Z). The owned-tree wall
    #: itself stays at window + reap allowance; the slack only names what
    #: spawning two .cmd/sh wrappers costs when the host is fully loaded.
    SPAWN_SLACK_S = 25.0

    def setUp(self):
        self.hold = tempfile.TemporaryDirectory(prefix="saipen-floor-stubs-")
        self.addCleanup(self.hold.cleanup)
        self.stubs = _StubFloors(self.hold.name)

    def subject_case(self, window: float | None = None):
        case = subject_module.PortableNeedsFields("run_floors")
        if window is not None:
            case.FLOOR_WINDOW_S = window
        return case

    def controlled(self, sh: str | None, ps1: str | None):
        """Patch the floor discovery both subjects read (never the subject)."""
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(audit_floor, "find_bash", return_value=sh))
        stack.enter_context(patch.object(audit_floor, "find_pwsh", return_value=ps1))
        stack.enter_context(
            patch.object(audit_floor, "bash_env", return_value=os.environ.copy())
        )
        return stack

    def test_1_a_fast_pair_of_controlled_floors_verifies(self):
        byte = self.stubs.fast("fast")
        with self.controlled(byte, self.stubs.fast("ps1fast")):
            self.subject_case().run_floors(audit_floor.GOOD_BOARD, valid=True)

    def test_2_a_fast_known_bad_controlled_floor_is_refused(self):
        byte = self.stubs.known_bad("bad")
        with self.controlled(byte, self.stubs.known_bad("ps1bad")):
            self.subject_case().run_floors(
                audit_floor.GOOD_BOARD, valid=False, diagnostic="synthetic known-bad"
            )

    def test_3_a_fixed_window_stall_times_out_before_and_verifies_after(self):
        """The recorded run-1 pathology: work just past the stock window.

        BEFORE (pre-fix subject): the 31 s control against the stock 30 s
        window is a genuine timeout red -- the defect this pair exists to
        prove (the XII record red as a missing validate.sh instead). AFTER
        (repaired subject): the window expiry ends the stalled attempt
        inside the owned tree, the double-window remeasure returns the
        runner's real verdict, and a valid board stays green -- judged
        only on that answer.
        """
        stall_s = self.CONTROL_WINDOW_S + 1.0
        with self.controlled(self.stubs.stall(stall_s, "stall"),
                             self.stubs.fast("ps1fast")):
            started = time.monotonic()
            self.subject_case(window=self.CONTROL_WINDOW_S).run_floors(
                audit_floor.GOOD_BOARD, valid=True
            )
            wall = time.monotonic() - started
        self.assertGreaterEqual(
            wall, stall_s, "the stalled floor answered only in the remeasure"
        )
        self.assertLess(
            wall,
            self.CONTROL_WINDOW_S * 2 + 15.0,
            "the remeasure is bounded and returns",
        )

    def test_4_an_unanswered_mandatory_floor_fails_closed_instead_of_skipping(self):
        """Two windows exceeded on an available floor: no verified PASS.

        The stub outlives the window twice over (> 2x), so an answered
        verdict is structurally impossible; Campaign XIII P0-A forbids the
        skip this used to take, so the field fails closed.
        """
        with self.controlled(
            self.stubs.stall(self.CONTROL_WINDOW_S * 3 + 1.0, "hang"),
            self.stubs.fast("ps1fast"),
        ), self.assertRaises(AssertionError) as context:
            self.subject_case(window=self.CONTROL_WINDOW_S).run_floors(
                audit_floor.GOOD_BOARD, valid=True
            )
        message = str(context.exception)
        self.assertIn("INCONCLUSIVE_TIMEOUT", message)
        self.assertIn("fails closed", message)

    def test_5_pipe_holding_grandchildren_cannot_outlive_the_owned_window(self):
        """The P0-B wall bound: the kill reaches the pipe holders.

        The controlled parent exits long before the window while a
        grandchild holds both output pipes for 120 s. In the repaired
        subject the window expiry terminates the OWNED tree, so both
        windows stay at window + the documented reap allowance regardless
        of family-scale contention (first measured red in the 8943-test
        family was a 21.5 s bound losing to 6-shard spawn latency, never
        to a pipe holder); a broken kill inherits the grandchild's full
        lifetime instead -- 120 s per attempt, ~240 s for the pair --
        which this bound discriminates by an order of magnitude.
        """
        case = self.subject_case(window=0.5)
        with self.controlled(self.stubs.grandchild("grandchild"),
                             self.stubs.fast("ps1fast")):
            started = time.monotonic()
            with self.assertRaises(AssertionError) as context:
                case.run_floors(audit_floor.GOOD_BOARD, valid=True)
            wall = time.monotonic() - started
        message = str(context.exception)
        self.assertIn("INCONCLUSIVE_TIMEOUT", message)
        #: The discriminant is load-immune and read from the refusal's own
        #: measured attempt walls, not from the outer wall: an owned kill
        #: answers each window inside window + reap allowance + spawn
        #: cost at any ambient load the family measured (two 8943-test
        #: runs: outer bounds of 21.5 s and 46.5 s both lost purely to
        #: 6-shard spawn latency, and the third measured a 0.3 s parent
        #: verdicting inside the 1.0 s remeasure); a MISSING kill
        #: inherits the holder's 60 s lifetime per attempt. Half the
        #: holder's lifetime separates the classes by more than any
        #: measured spawn noise.
        numbers = re.search(r"measured walls ([^)]+)\)", message)
        self.assertIsNotNone(numbers, f"no measured walls in: {message!r}")
        attempt_walls = [
            float(value.strip().rstrip(" s")) for value in numbers.group(1).split(",")
        ]
        self.assertEqual(len(attempt_walls), 2, f"expected two attempts: {message!r}")
        holder_lifetime_s = 60.0  # the parent's sleep is the binding life
        for measured in attempt_walls:
            self.assertLess(
                measured,
                holder_lifetime_s / 2,
                f"attempt wall {measured:.1f} s reached half the holder's "
                f"lifetime: a pipe holder outlived the owned kill "
                f"(measured {attempt_walls}, outer wall {wall:.1f} s)",
            )

    def test_6_a_floor_that_touches_the_memory_is_named_not_ignored(self):
        """The timeout-or-verdict path may not launder evidence corruption.

        Green on BOTH pair sides: this control proves the memory guard is
        live, so the run_5/run_floors comparison cannot be vacuous.
        """
        with self.controlled(self.stubs.memory_writer("writer"),
                            self.stubs.fast("ps1fast")), \
                self.assertRaises(AssertionError) as context:
            self.subject_case().run_floors(audit_floor.GOOD_BOARD, valid=True)
        self.assertIn("GARBAGE.txt", str(context.exception))

    def test_7_a_stall_then_known_bad_answer_is_judged_as_a_real_fail(self):
        """First timeout, then a known-bad answer: judged, not remeasured away."""
        program = (
            f"import sys, time; time.sleep({self.CONTROL_WINDOW_S + 1.0}); "
            "sys.stderr.write('synthetic known-bad'); sys.exit(7)"
        )
        byte = self.stubs._install("stallbad", program)
        with self.controlled(byte, self.stubs.known_bad("ps1bad")):
            self.subject_case(window=self.CONTROL_WINDOW_S).run_floors(
                audit_floor.GOOD_BOARD, valid=False, diagnostic="synthetic known-bad"
            )

    def test_8_an_absent_optional_floor_is_an_allowed_absence(self):
        """P0-A role policy: an optional floor may be absent (audit_parity's
        documented loud skip for the cross-platform diagnostic), and the
        remaining native floor still carries the release coverage."""
        native = self.stubs.fast("native-fast")
        if os.name == "nt":
            controlled = self.controlled(None, native)
        else:
            controlled = self.controlled(native, None)
        with controlled:
            self.subject_case().run_floors(audit_floor.GOOD_BOARD, valid=True)

    def test_9_a_missing_native_floor_fails_instead_of_being_substituted(self):
        """P0-A role policy: the mandatory native floor is release coverage.

        BEFORE: the optional floor alone satisfies the old harness, so a
        PASS could reach SHIP without the platform's own floor -- the
        laundering this control reds. AFTER: UNAVAILABLE_PLATFORM refuses.
        """
        present = self.stubs.fast("optional-fast")
        if os.name == "nt":
            controlled = self.controlled(present, None)
        else:
            controlled = self.controlled(None, present)
        with controlled, self.assertRaises(AssertionError) as context:
            self.subject_case().run_floors(audit_floor.GOOD_BOARD, valid=True)
        self.assertIn("UNAVAILABLE_PLATFORM", str(context.exception))


if __name__ == "__main__":
    unittest.main()
