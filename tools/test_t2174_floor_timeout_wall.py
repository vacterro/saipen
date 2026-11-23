"""T-2174: the floor-timeout oracle must stay cheap enough for routine runs.

The nine P0-A/B/C controls in ``test_t2163_floor_timeout_remeasure`` are
mandatory, but their synthetic stalls used the production 30 s / 60 s window
literally: three tests waited 31 s, 91 s and 31 s for a measured 214.8 s
module wall. The oracle may scale its controlled windows and stub lifetimes
together -- the verdict classes, the owned-tree kill and the fail-closed
refusal are what the controls prove, not the literal number of seconds.

This test pins the resulting wall contract as a subprocess measurement, so a
future change that restores host-scale waits fails here without a 35-minute
family run.
"""

from __future__ import annotations

import subprocess
import sys
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
TARGET = TOOLS / "test_t2163_floor_timeout_remeasure.py"
WALL_BUDGET_S = 90.0
EXPECTED_TEST_COUNT = 9


class FloorTimeoutWallTests(unittest.TestCase):
    def test_timeout_oracle_keeps_all_controls_inside_wall_budget(self):
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, str(TARGET)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        wall = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn(f"Ran {EXPECTED_TEST_COUNT} tests", result.stderr)
        self.assertLess(
            wall,
            WALL_BUDGET_S,
            f"floor-timeout oracle wall {wall:.1f} s exceeded "
            f"{WALL_BUDGET_S:.0f} s; mandatory controls must not wait on "
            f"host-scale timeouts",
        )


if __name__ == "__main__":
    unittest.main()
