"""Diagnostic rerun of the exact failed test IDs; not a full-family record."""
import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
record = json.loads((ROOT / ".saipen/evidence/core-unit/f7662308cbc6556a-20261023T051543856290Z.json").read_text())
began = time.monotonic()
suite = unittest.defaultTestLoader.loadTestsFromNames(record["red"])
result = unittest.TextTestRunner(verbosity=2).run(suite)
summary = {
    "kind": "diagnostic exact-prior-failure selection, not publication evidence",
    "source_record": "f7662308cbc6556a-20261023T051543856290Z.json",
    "selected_ids": record["red"],
    "ran": result.testsRun,
    "failures": [str(case) for case, _ in result.failures],
    "errors": [str(case) for case, _ in result.errors],
    "elapsed_s": round(time.monotonic()-began, 3),
}
tag = sys.argv[1] if len(sys.argv) == 2 else "rerun1"
if tag not in {"rerun1", "rerun2", "rerun3"}:
    raise ValueError("unknown evidence output tag")
Path(__file__).with_name(f"prior-failure-{tag}.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
raise SystemExit(0 if result.wasSuccessful() else 1)
