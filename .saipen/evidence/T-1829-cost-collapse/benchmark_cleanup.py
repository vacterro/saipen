"""One measured real-platform acceptance module; no canonical suite."""
import datetime as dt
import functools
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit
from saipen_engine.inflight import holding

output = Path(sys.argv[1])
original = core_unit.run_family
runs = []


@functools.wraps(original)
def observed(*args, **kwargs):
    result = original(*args, **kwargs)
    runs.append({key: result.get(key) for key in (
        "status", "ran", "jobs", "duration_s", "timings_s", "copy_metrics", "sandboxes_leaked")})
    return result


started_utc = dt.datetime.now(dt.timezone.utc).isoformat()
start = time.monotonic()
suite = unittest.TestLoader().discover("tools", pattern="test_t1505_core_unit_sandbox_reclaim.py")
with holding(ROOT, "T-1830", "scoped cleanup baseline"), patch.object(core_unit, "run_family", observed):
    result = unittest.TextTestRunner(verbosity=2).run(suite)
payload = {"schema": 1, "kind": "scoped-real-platform-benchmark", "started_utc": started_utc,
           "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
           "duration_s": time.monotonic() - start, "ran": result.testsRun,
           "status": "PASS" if result.wasSuccessful() else "FAIL", "family_runs": runs,
           "scope": "test_t1505_core_unit_sandbox_reclaim.py"}
output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload))
sys.exit(0 if result.wasSuccessful() else 1)
