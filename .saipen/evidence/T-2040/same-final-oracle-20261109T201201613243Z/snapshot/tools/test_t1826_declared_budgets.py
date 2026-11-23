"""T-1826: declared budgets clear the measured cost they were meant to cover.

Two bounds answered "no" to work that had already succeeded:

* `test_runner._families()` declared 5400 s for the unit family, chosen when the
  family was 3475 tests and a run cost 2254 s (T-1344). At 6925 tests the same
  single-process run measured 6879.7 s clean
  (`.saipen/evidence/core-unit/4938af3e6ed9afc4-20261019T225802Z.json`) and
  7458.0 s on a loaded host
  (`.saipen/evidence/core-unit/73e01d794f842e8c-20261020T010550Z.json`), so
  `core_unit.py evidence` recorded TIMEOUT for a suite that was green.

* The OpenCode adapter ran every canonical check as its own child process with
  a 15000 ms bound. A measured `response check --classify --operational-turn`
  on a fresh copy of this tree cost 20.19 s cold and 12.11 s warm, and 15.67 s
  per call at six-way concurrency. Under host load the adapter therefore killed
  a HEALTHY engine and reported `EXEC_RESPONSE_INVALID: ETIMEDOUT`, which is how
  two `test_t1553 RealLauncherInit` cases went red inside a family run.

A budget is not a prediction. It is a bound that must clear a recorded
measurement with headroom large enough that ordinary host load cannot cross it.
These tests hold both bounds to the numbers actually observed, so shrinking one
back below its measurement fails here instead of producing a timeout verdict
somewhere expensive and unrelated.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from saipen_engine import test_runner  # noqa: E402

#: The slowest single-process family run on record, with its record id. Every
#: entry is a `.saipen/evidence/core-unit/` record that `core_unit.evidence`
#: wrote; the family runs in a copy without `.saipen/`, so the values are
#: embedded with their provenance rather than read at test time.
MEASURED_FAMILY_RUNS = {
    "4938af3e6ed9afc4-20261019T225802Z": 6879.7,  # --jobs 1, clean tree, PASS
    "73e01d794f842e8c-20261020T010550Z": 7458.0,  # --jobs 1, loaded host, 2 red
}
#: Headroom a bound must carry over its measurement: a fifth of the measured
#: cost, so a repeat run on a busy host does not cross it.
HEADROOM_FACTOR = 1.2

#: The adapter's child processes, measured on this host 2026-10-20 against a
#: fresh copy of the tree (`response check --classify --operational-turn`).
MEASURED_CHECK_MS = {"cold": 20190, "warm": 12110, "six_way_concurrent": 15670}

GUARD_JS = ROOT / "extensions" / "adapters" / "opencode" / "saipen-guard.js"
CLAUDE_HOOK = ROOT / "extensions" / "adapters" / "claude" / "saipen-guard.py"
T1553 = TOOLS / "test_t1553_mid_session_activation.py"


def _js_constant(text: str, name: str) -> int:
    match = re.search(rf"^const {name} = (\d+);$", text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"{name} is not declared as a plain integer constant")
    return int(match.group(1))


class FamilyBudgetTests(unittest.TestCase):
    """The unit family budget must clear the family's own measured duration."""

    def test_the_unit_family_budget_clears_every_measured_run(self) -> None:
        declared = test_runner._families()[0]
        self.assertEqual(declared.name, "unit")
        worst = max(MEASURED_FAMILY_RUNS.values())
        self.assertGreaterEqual(
            declared.timeout,
            worst * HEADROOM_FACTOR,
            f"the declared unit family budget {declared.timeout} s does not clear "
            f"the measured worst case {worst} s with {HEADROOM_FACTOR}x headroom",
        )

    def test_the_family_budget_is_not_below_a_run_that_already_timed_out(self) -> None:
        """5400 s is the value this ticket measured as a false TIMEOUT."""
        declared = test_runner._families()[0]
        worst = max(MEASURED_FAMILY_RUNS.values())
        self.assertGreater(
            declared.timeout,
            worst,
            f"a budget of {declared.timeout} s is still below the recorded "
            f"{worst} s run, so canonical evidence will time out a green suite",
        )

    def test_core_unit_consumes_the_declared_family_and_nothing_else(self) -> None:
        declared = test_runner._families()[0]
        self.assertEqual(core_unit.family().timeout, declared.timeout)
        self.assertEqual(core_unit.family().command, declared.command)


class AdapterCheckBudgetTests(unittest.TestCase):
    """The host adapter's child bound must clear the measured engine cost."""

    def test_the_open_guard_bound_clears_the_measured_check_cost(self) -> None:
        text = GUARD_JS.read_text(encoding="utf-8")
        bound = _js_constant(text, "GUARD_TIMEOUT_MS")
        slowest = max(MEASURED_CHECK_MS.values())
        self.assertGreaterEqual(
            bound,
            int(slowest * HEADROOM_FACTOR),
            f"the adapter kills its child after {bound} ms while a healthy check "
            f"measured {slowest} ms; that bound reports EXEC_RESPONSE_INVALID: "
            f"ETIMEDOUT for a slower host, not a defect",
        )

    def test_the_open_guard_bound_is_not_below_its_sibling_transports(self) -> None:
        """Claude's hook already answers 45 s; only OpenCode invented a third."""
        claude = CLAUDE_HOOK.read_text(encoding="utf-8")
        match = re.search(r"^CHECK_TIMEOUT_SECONDS = (\d+)$", claude, re.MULTILINE)
        if match is None:
            raise AssertionError("the Claude hook no longer declares CHECK_TIMEOUT_SECONDS")
        sibling_ms = int(match.group(1)) * 1000
        opencode_ms = _js_constant(GUARD_JS.read_text(encoding="utf-8"), "GUARD_TIMEOUT_MS")
        self.assertGreaterEqual(
            opencode_ms,
            sibling_ms,
            f"OpenCode waits {opencode_ms} ms for the same engine call Claude "
            f"allows {sibling_ms} ms",
        )

    def test_the_launcher_harness_outlasts_the_adapter_bound(self) -> None:
        """A harness bound under the adapter's would cut the adapter off first."""
        harness = T1553.read_text(encoding="utf-8")
        spawn_bounds = [int(value) for value in re.findall(r"timeout: (\d+),", harness)]
        self.assertTrue(spawn_bounds, "the launcher harness declares no spawnSync bound")
        adapter_ms = _js_constant(GUARD_JS.read_text(encoding="utf-8"), "GUARD_TIMEOUT_MS")
        self.assertGreater(
            min(spawn_bounds),
            adapter_ms,
            f"the harness kills a turn after {min(spawn_bounds)} ms but the adapter "
            f"may legitimately run its child for {adapter_ms} ms",
        )


if __name__ == "__main__":
    unittest.main()
