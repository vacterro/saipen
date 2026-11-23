"""Measure read-only detector cost; synthetic observations are not release evidence."""

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import closed_contracts
from test_t1726_closed_contracts import ClosedContracts


def sample(root):
    times = []
    for _ in range(5):
        started = time.perf_counter()
        observation = closed_contracts.inspect(root, limit=0)
        times.append((time.perf_counter() - started) * 1000)
    return {
        "samples_ms": times,
        "median_ms": statistics.median(times),
        "ok": observation["ok"],
        "total": observation["total"],
        "counts": observation["counts"],
        "paths_read": observation["paths_read"],
        "bytes_read": observation["bytes_read"],
        "errors": observation["errors"],
        "blocks_unrelated_work": observation["blocks_unrelated_work"],
    }


result = {"actual_project": sample(ROOT), "synthetic": []}
case = ClosedContracts("test_unrelated_edit_does_not_invalidate_focused_observation")
try:
    case.setUp()
    baseline = case.recheck()
    assert baseline["closed_contract"]["status"] == "CURRENT_PASS", baseline
    unrelated = case.root / "unrelated"
    unrelated.mkdir()
    previous = 0
    for size in (0, 1000, 10000):
        for index in range(previous, size):
            (unrelated / f"file-{index:05d}.txt").write_text("unrelated\n", encoding="utf-8")
        previous = size
        result["synthetic"].append({"unrelated_files": size, **sample(case.root)})
finally:
    case.doCleanups()

target = Path(__file__).with_name("performance-current.json")
target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
