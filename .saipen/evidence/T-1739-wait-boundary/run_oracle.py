"""Run the unchanged boundary oracle, optionally against a deliberate bad projector."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import automation

parser = argparse.ArgumentParser()
parser.add_argument("--mutate-wait", action="store_true")
args = parser.parse_args()
original = automation._routing_disposition


def bad_projection(routed, action, reason):
    if reason == "wait":
        return automation.CONTINUE, "deliberate-ignored-wait"
    return original(routed, action, reason)


suite = unittest.defaultTestLoader.discover(str(ROOT / "tools"), "test_t1739_wait_boundary.py")
stream = io.StringIO()
with patch.object(automation, "_routing_disposition", bad_projection if args.mutate_wait else original):
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
name = "oracle-red" if args.mutate_wait else "oracle-green"
record = {"oracle_sha256": hashlib.sha256((ROOT / "tools/test_t1739_wait_boundary.py").read_bytes()).hexdigest(),
          "deliberate_mutation": args.mutate_wait, "ran": result.testsRun,
          "failures": [str(case) for case, _ in result.failures],
          "errors": [str(case) for case, _ in result.errors], "passed": result.wasSuccessful()}
(HERE / (name + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
(HERE / (name + ".txt")).write_text(stream.getvalue(), encoding="utf-8")
print(json.dumps(record))
raise SystemExit(0 if result.wasSuccessful() else 1)
