"""Fixed prospective T-1597 oracle: one transient empty sweep, real retry."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from test_hermetic_env import hermetic_env


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    label, path = sys.argv[1:3]
    subject_path = Path(path).resolve()
    module = types.ModuleType("sandbox_wait_subject")
    module.__file__ = str(ROOT / "tools/test_t1505_core_unit_sandbox_reclaim.py")
    sys.modules[module.__name__] = module
    stream = io.StringIO()
    calls = []
    with patch.dict("os.environ", hermetic_env(), clear=True):
        exec(compile(subject_path.read_bytes(), str(subject_path), "exec"), module.__dict__)
        real_sweep = module.core_unit.sweep_stale_sandboxes

        def transient_empty(root, **kwargs):
            calls.append(str(root))
            # Model a documented transient REPORT, not an arbitrary eventual
            # success: after the first call use the real sweeper on real bytes.
            if len(calls) == 1 or label == "bad-permanent-empty":
                return []
            return real_sweep(root, **kwargs)

        test = module.HeldSandboxTests(
            "test_a_held_sandbox_is_reported_then_swept_once_its_owner_is_gone")
        with patch.object(module.core_unit, "sweep_stale_sandboxes", transient_empty):
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.TestSuite([test]))
    report = {"label": label, "verifier_sha256": sha(Path(__file__)),
              "subject_sha256": sha(subject_path), "subject": str(subject_path),
              "production_sha256": sha(ROOT / "tools/saipen_engine/core_unit.py"),
              "ran": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped), "sweep_calls": len(calls),
              "successful": result.wasSuccessful(),
              "scope": "Controlled transient empty-sweep contract; not a claim to reproduce the original intermittent shard failure's mechanism."}
    (HERE / f"{label}.txt").write_text(stream.getvalue(), encoding="utf-8")
    (HERE / f"{label}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 0 if result.wasSuccessful() and result.testsRun > 0 and not result.skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
