"""Fixed external instrument for the T-1597 test-control subject.

Two not-yet-reclaimable sweep observations model delayed Windows handle release.
The subject must tolerate these observations, sweep the actual dead-owner tree,
and preserve the live-owner protection already exercised by its own module.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd() / "tools"))
from saipen_engine import core_unit
from test_t1505_core_unit_sandbox_reclaim import HeldSandboxTests

real_sweep = core_unit.sweep_stale_sandboxes
observations = 0


def lagged_sweep(*args, **kwargs):
    global observations
    observations += 1
    if observations <= 2:
        return []
    return real_sweep(*args, **kwargs)


with patch.object(core_unit, "sweep_stale_sandboxes", side_effect=lagged_sweep):
    suite = unittest.TestSuite([HeldSandboxTests(
        "test_a_held_sandbox_is_reported_then_swept_once_its_owner_is_gone")])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
if result.wasSuccessful():
    assert observations >= 3, "the delayed sweep was never observed"
print("sweep_observations=" + str(observations))
raise SystemExit(0 if result.wasSuccessful() else 1)
