"""Reuse the established immutable prevention controls with fresh output paths."""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
label = sys.argv[1]
if Path(label).name != label:
    raise SystemExit("invalid label")
destination = HERE / label
if destination.exists():
    raise SystemExit("existing evidence is immutable")
destination.mkdir()
source = ROOT / ".saipen/evidence/T-1706-hot-switch/regression_control_v3.py"
spec = importlib.util.spec_from_file_location("t1705_prevention_controls", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
# Only output paths change. Command, fixtures, oracle and subject selection stay.
module.HERE = destination
sys.exit(module.main())
