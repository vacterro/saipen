"""Capture isolated draft verification, without admitting live Work."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.core_unit import parse_output, tree_fingerprint  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("label")
parser.add_argument("modules", nargs="+")
args = parser.parse_args()
location = json.loads((evidence / "location.json").read_text(encoding="utf-8"))
subject = Path(location["subject"])
argv = [sys.executable, "-B", "-m", "unittest", *args.modules]
before = tree_fingerprint(subject)
started = time.time()
result = subprocess.run(argv, cwd=subject, capture_output=True, text=True, encoding="utf-8",
                        errors="backslashreplace", env=os.environ.copy())
elapsed = time.time() - started
stdout = evidence / f"{args.label}.stdout.txt"
stderr = evidence / f"{args.label}.stderr.txt"
stdout.write_text(result.stdout, encoding="utf-8")
stderr.write_text(result.stderr, encoding="utf-8")
live_canonical = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                  for name in location["canonical_sha256"]}
live_fingerprint = tree_fingerprint(root)
summary = {"argv": argv, "cwd": str(subject), "exit_code": result.returncode,
           "elapsed_seconds": elapsed, "fingerprint_before": before,
           "fingerprint_after": tree_fingerprint(subject), "counts": parse_output(result.stderr),
           "stdout_sha256": hashlib.sha256(stdout.read_bytes()).hexdigest(),
           "stderr_sha256": hashlib.sha256(stderr.read_bytes()).hexdigest(),
           "live_source_fingerprint": live_fingerprint,
           "live_canonical_sha256": live_canonical,
           "live_root_modified": (live_fingerprint != location["baseline_fingerprint"]
                                  or live_canonical != location["canonical_sha256"]),
           "live_persistent_grant": False}
(evidence / f"{args.label}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
raise SystemExit(result.returncode)
