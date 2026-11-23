"""T-1286: the crew-launcher probe gives one verdict whatever the timing.

bootstrap/saipen_crew.sh judged each terminal launcher after a fixed sleep
(the probe used 0.05 s): a launcher still running then was taken for a live
terminal. A failing shim that was merely slow to start therefore "launched":
rc 0, Done. Launched 3 crew windows, and 3 of the expected 9 calls -- the
flake the hostile suite reported as a launcher regression. The launcher now
judges a launcher the moment it exits, so the probe affords a generous grace,
and its messages tell a hung launcher from one that ran too few launchers.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_scenarios as rs  # noqa: E402

BASH = rs.find_bash()
LAUNCHER = rs.HOME / "bootstrap" / "saipen_crew.sh"

#: The judgement before T-1286, kept as the pre-fix subject of the red control.
FIXED_GRACE_RUN_DETACHED = """run_detached() {
  "$@" &
  pid=$!
  sleep "${SAIPEN_CREW_LAUNCH_GRACE:-1}"
  if kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  wait "$pid"
}
"""

SAIHUNT_ROLE = (
    '  "SAIPEN saihunt|saihunt / sensor    -> type: saihunt   (spawn+adopt, hunt on loop)" \\\n'
)


@unittest.skipUnless(BASH, "no usable bash")
class CrewShProbeTests(unittest.TestCase):
    def variant(self, transform) -> Path:
        """A copy of the launcher with one deliberate change."""
        base = Path(tempfile.mkdtemp(prefix="saipen-t1286-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        (base / "bootstrap").mkdir()
        target = base / "bootstrap" / "saipen_crew.sh"
        source = LAUNCHER.read_text(encoding="utf-8")
        changed = transform(source)
        self.assertNotEqual(changed, source, "the variant changed nothing")
        target.write_text(changed, encoding="utf-8", newline="\n")
        return target

    def assert_problem(self, problems: list[str], *fragments: str) -> None:
        self.assertTrue(
            any(all(fragment in problem for fragment in fragments) for problem in problems),
            f"no problem carries {fragments}: {problems}",
        )

    def test_the_launcher_passes_both_cases(self):
        problems, passes = rs.probe_crew_sh(BASH, LAUNCHER)
        self.assertEqual(problems, [])
        self.assertEqual(len(passes), 2)

    def test_a_slow_starting_shim_gets_the_same_verdict(self):
        problems, passes = rs.probe_crew_sh(BASH, LAUNCHER, shim_delay=0.3)
        self.assertEqual(problems, [])
        self.assertEqual(len(passes), 2)

    def test_red_control_the_fixed_grace_launcher_takes_a_slow_failure_for_a_window(self):
        def restore_fixed_grace(source: str) -> str:
            start = source.index("run_detached() {")
            end = source.index("\n}\n", start) + len("\n}\n")
            return source[:start] + FIXED_GRACE_RUN_DETACHED + source[end:]

        script = self.variant(restore_fixed_grace)
        problems, _ = rs.probe_crew_sh(BASH, script, grace="0.05", shim_delay=0.3)
        self.assert_problem(problems, "broken launcher", "(rc=0)")

    def test_red_control_a_launcher_that_skips_a_role(self):
        script = self.variant(lambda source: source.replace(SAIHUNT_ROLE, ""))
        problems, _ = rs.probe_crew_sh(BASH, script)
        self.assert_problem(problems, "broken launcher", "observed only 6 of 9 calls after")
        self.assert_problem(problems, "working launcher", "observed only 2 of 3 calls after")

    def test_red_control_a_shim_that_never_runs(self):
        script = self.variant(lambda source: source.replace('  "$@" &\n', "  true &\n", 1))
        problems, _ = rs.probe_crew_sh(BASH, script)
        self.assert_problem(problems, "broken launcher", "observed only 0 of 9")
        self.assert_problem(problems, "working launcher", "observed only 0 of 3")

    def test_a_hung_launcher_is_reported_as_a_timeout(self):
        script = self.variant(
            lambda source: source.replace("\nlaunched=0\n", "\nsleep 4\nlaunched=0\n", 1)
        )
        problems, _ = rs.probe_crew_sh(BASH, script, timeout=1)
        self.assert_problem(problems, "broken launcher", "timed out after 1s waiting")


if __name__ == "__main__":
    unittest.main()
