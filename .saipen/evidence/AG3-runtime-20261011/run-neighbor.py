"""Capture a focused neighboring gate without losing completion output."""
import json
import subprocess
import sys
from pathlib import Path

stage, root, pattern = sys.argv[1:]
output = Path(__file__).resolve().parent / (stage + ".json")
if output.exists():
    raise SystemExit("Gate evidence already exists")
command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools", "-p", pattern]
run = subprocess.run(command, cwd=root, capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=900)
output.write_text(json.dumps({"root": root, "command": command, "exit_code": run.returncode,
                              "stdout": run.stdout, "stderr": run.stderr}, indent=2) + "\n",
                  encoding="utf-8")
print(json.dumps({"stage": stage, "exit_code": run.returncode, "evidence": str(output)}))
print(run.stderr[-12000:])
raise SystemExit(run.returncode)
