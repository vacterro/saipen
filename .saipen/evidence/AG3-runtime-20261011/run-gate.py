"""Preserve exact output for one local gate."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
stage, *arguments = sys.argv[1:]
output = HERE / (stage + ".json")
if output.exists():
    raise SystemExit("Gate evidence already exists")
command = [sys.executable, "-B", *arguments]
run = subprocess.run(command, cwd=HERE.parents[2], capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=900)
output.write_text(json.dumps({"command": command, "exit_code": run.returncode,
                              "stdout": run.stdout, "stderr": run.stderr}, indent=2) + "\n",
                  encoding="utf-8")
print(json.dumps({"stage": stage, "exit_code": run.returncode, "evidence": str(output)}))
print((run.stdout + run.stderr)[-2500:])
raise SystemExit(run.returncode)
