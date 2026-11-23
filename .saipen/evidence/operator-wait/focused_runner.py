"""Declared focused neighboring family; records executed aggregate evidence."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
MODULES = (
    "test_next_action_grammar", "test_next_action_deadlock", "test_refusal_registry",
    "test_state_scalar_quoting", "test_protocol_registry", "test_continue_entry",
    "test_continue_chain", "test_recovery_reachability", "test_reconcile_valve",
    "test_user_wait_release",
)


def main():
    label = sys.argv[1]
    path = HERE / f"focused-{label}.json"
    if path.exists():
        raise SystemExit(f"refusing to overwrite evidence: {path}")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    )
    record = {
        "modules": MODULES, "verifier": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "ran": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "passed": result.wasSuccessful(),
        "transcript": stream.getvalue(),
    }
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in record.items() if key != "transcript"}))
    if not result.wasSuccessful():
        print(record["transcript"][-10000:])
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
