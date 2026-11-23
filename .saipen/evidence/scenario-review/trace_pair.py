"""Observe refused fixture transitions without changing the fixed oracle."""
from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import operations

real_transition = operations.transition_phase
refusals = []


def observed_transition(*args, **kwargs):
    result = real_transition(*args, **kwargs)
    if not result.get("ok"):
        refusals.append({"root": str(args[0]), "phase": args[1],
                         "result": result.to_dict()})
    return result


sys.argv = [str(HERE / "run_pair.py"), "red-confirm",
            str(ROOT / ".saipen/evidence/scenario-oracles/run_scenarios.before.py")]
try:
    with patch.object(operations, "transition_phase", observed_transition):
        runpy.run_path(str(HERE / "run_pair.py"), run_name="__main__")
finally:
    (HERE / "transition-refusals.json").write_text(
        json.dumps(refusals, indent=2) + "\n", encoding="utf-8")
