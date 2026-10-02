"""Run the real phase-rename probe and record its unmodified verdict."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import audit_checks as audit

with tempfile.TemporaryDirectory(prefix="saipen-t1581-live-") as temporary:
    context = audit.ProbeContext(Path(temporary), list(audit.CASES), None)
    setup_error = audit.build_pristine(context)
    if setup_error:
        raise RuntimeError(setup_error)
    baseline_error = audit.validator_baseline_probe(context)
    if baseline_error:
        raise RuntimeError(baseline_error)
    error = audit.phase_rename_probe(context.pristine, Path(temporary))
    result = {"probe": "phase-rename", "verdict": "FAIL" if error else "PASS",
              "error": error, "baseline": "PASS", "tree": str(ROOT)}
    target = ROOT / ".saipen/evidence/T-1581-phase-rename-20261001.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if error else 0)
