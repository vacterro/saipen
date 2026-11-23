"""T-2062 regression oracle: GC maintenance checkpoints serialize across concurrent DONE closures.

Derived from the saipython PY-19 (kitchen/pen/T-2062-r4) verification harness:
eight bounded disposable Git projects, two concurrent maintenance_checkpoint
calls each; the serialized implementation must count both DONE closures,
run exactly one maintenance pass, leave no durable failures, and record the
protected-budget debt. The pre-serialization gc.py reproduces the
lost-checkpoint race and fails this oracle.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "tools"))
import saipen_engine  # noqa: E402

from saipen_engine import gc  # noqa: E402


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60)


def _one_iteration(index: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="t2062-oracle-%d-" % index) as tmp:
        root = Path(tmp)
        (root / ".saipen").mkdir()
        (root / ".saipen" / "LOG.md").write_text(
            "# Log\n"
            "- 16.11.26 00:00 [E-001] [T-001] [op: finish-one] RUN: T-001 -> DONE\n"
            "- 16.11.26 00:01 [E-002] [T-002] [op: finish-two] RUN: T-002 -> DONE\n",
            encoding="utf-8",
        )
        evidence = root / ".saipen" / "evidence" / "canonical.json"
        evidence.parent.mkdir(parents=True)
        evidence.write_bytes(b'{"protected": true}\n')
        state = gc._default_state()
        state["config"]["interval_done"] = 2
        state["config"]["evidence_budget_gib"] = 1.0 / (1024**3)
        gc.save_state(root, state)
        for args in (
            ("init",),
            ("config", "user.name", "t2062"),
            ("config", "user.email", "t2062@example.invalid"),
            ("add", "-A"),
            ("commit", "-m", "bounded fixture"),
        ):
            _git(root, *args)

        start = threading.Barrier(3)

        def checkpoint(worker: int) -> dict:
            start.wait(timeout=5)
            return gc.maintenance_checkpoint(root, "t2062-%d-%d" % (index, worker))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(checkpoint, worker) for worker in range(2)]
            start.wait(timeout=5)
            results = [future.result(timeout=10) for future in futures]

        state = gc.load_state(root)
        total = gc.canonical_total(root, state)
        failures = gc.maintenance_failures(root)
        result = {
            "iteration": index,
            "result_codes": [item.get("code") for item in results],
            "counted_done": state.get("counted_done"),
            "canonical_done": total.get("union"),
            "maintenance_debt": (state.get("maintenance") or {}).get("state"),
            "maintenance_runs": len(state.get("runs") or []),
            "durable_failures": len(failures),
        }
        if (
            "GC_MAINTENANCE_FAILED" in result["result_codes"]
            or result["counted_done"] != ["T-001", "T-002"]
            or result["canonical_done"] != ["T-001", "T-002"]
            or result["maintenance_debt"] != gc.DEBT_BLOCKED_PROTECTED_BUDGET
            or result["maintenance_runs"] != 1
            or result["durable_failures"] != 0
        ):
            raise AssertionError(json.dumps(result, sort_keys=True))
        return result


class T2062GcSerialization(unittest.TestCase):
    def test_serialized_checkpoints(self) -> None:
        rounds = [_one_iteration(index) for index in range(8)]
        self.assertEqual(len(rounds), 8)
        for r in rounds:
            self.assertEqual(r["counted_done"], ["T-001", "T-002"])
            self.assertEqual(r["durable_failures"], 0)


if __name__ == "__main__":
    unittest.main()
