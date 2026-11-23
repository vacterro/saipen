"""Record a bounded preliminary A05 run without touching production or its ledger."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint


def main() -> None:
    stage = sys.argv[1]
    if stage not in {"red", "candidate", "red-v2", "candidate-v2", "red-v3", "candidate-v3", "candidate-v4", "candidate-v5"}:
        raise ValueError("supported preliminary stages are red and candidate")
    output = HERE / ("preliminary-" + stage + ".json")
    if output.exists():
        raise RuntimeError("phase artifact already exists; preserve it")
    descriptor = json.loads((HERE / "scratch-preparation.json").read_text(encoding="utf-8"))
    project = Path(descriptor["project"])
    baseline = tree_fingerprint(ROOT)
    oracle = project / "tools/test_reconcile_history_ledger_blocked.py"
    oracle_sha = hashlib.sha256(oracle.read_bytes()).hexdigest()
    subjects = {relative: hashlib.sha256((project / relative).read_bytes()).hexdigest()
                for relative in ("tools/saipen_engine/reconcile.py", "tools/saipen.py")}
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("SAIPEN_")}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    command = [sys.executable, "-B", str(oracle)]
    completed = subprocess.run(command, cwd=project, env=environment,
                               capture_output=True, timeout=90)
    if tree_fingerprint(ROOT) != baseline:
        raise RuntimeError("live source changed during preliminary isolated run")
    if hashlib.sha256(oracle.read_bytes()).hexdigest() != oracle_sha:
        raise RuntimeError("oracle changed during preliminary run")
    result = {"stage": stage, "command": command, "project": str(project),
              "exit_code": completed.returncode, "oracle_sha256": oracle_sha,
              "subject_files": subjects,
              "stdout": completed.stdout.decode("utf-8", errors="replace"),
              "stderr": completed.stderr.decode("utf-8", errors="replace"),
              "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
              "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
              "live_fingerprint": baseline, "live_source_unchanged": True,
              "limits": "Preliminary scratch proof while T-1713 owns VERIFY; not T-1714 phase evidence."}
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (HERE / (stage + ".stdout.bin")).write_bytes(completed.stdout)
    (HERE / (stage + ".stderr.bin")).write_bytes(completed.stderr)
    print(json.dumps({key: result[key] for key in
                      ("stage", "exit_code", "oracle_sha256", "subject_files", "live_source_unchanged")}))
    print(result["stderr"][-2000:])


if __name__ == "__main__":
    main()
