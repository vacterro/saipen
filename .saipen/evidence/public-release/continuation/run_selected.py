import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("group", choices=("injector", "freshness", "release"))
parser.add_argument("--label", required=True)
parser.add_argument("--root", type=Path)
args = parser.parse_args()
root = args.root or Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / "tools"))
import run_scenarios as scenarios

functions = {
    "injector": scenarios.run_injector_probes,
    "freshness": scenarios.run_release_freshness_probes,
    "release": scenarios.run_release_executor_probes,
}
started = time.monotonic()
stream = io.StringIO()
error = None
try:
    with scenarios.session_carrier_isolation(), contextlib.redirect_stdout(stream):
        result = functions[args.group]()
except Exception as exc:
    error = f"{type(exc).__name__}: {exc}"
    result = ([error], 0)
record = {
    "group": args.group, "root": str(root), "result": result,
    "error": error, "seconds": time.monotonic() - started,
    "output": stream.getvalue(),
}
out = Path(__file__).resolve().parent
(out / f"{args.label}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in record.items() if key != "output"}, indent=2))
raise SystemExit(1 if result[0] else 0)
