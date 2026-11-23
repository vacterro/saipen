"""Capture one native verification command without changing its oracle."""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

directory = Path(__file__).resolve().parent
root = directory.parents[2]
label, *command = sys.argv[1:]
env = os.environ.copy()
if command[0] == "--native-opencode":
    command.pop(0)
    native = Path(r"C:\nodejs\node_modules\opencode-ai\node_modules\opencode-windows-x64\bin")
    env["PATH"] = str(native) + os.pathsep + env.get("PATH", "")
command = [sys.executable if part == "{python}" else part for part in command]
record = {
    "command": command,
    "cwd": str(root),
    "started_utc": datetime.now(timezone.utc).isoformat(),
    "runner_pid": os.getpid(),
}
log_path = directory / (label + ".txt")
result_path = directory / (label + "-result.json")
if log_path.exists() or result_path.exists():
    raise SystemExit("Existing evidence preserved; select a fresh run label.")
start = time.monotonic()
with log_path.open("wb", buffering=0) as output:
    child = subprocess.Popen(command, cwd=root, env=env, stdout=output, stderr=subprocess.STDOUT)
    record["child_pid"] = child.pid
    print(json.dumps(record), flush=True)
    record["exit_code"] = child.wait()
record["elapsed_s"] = round(time.monotonic() - start, 3)
record["finished_utc"] = datetime.now(timezone.utc).isoformat()
result_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record), flush=True)
raise SystemExit(record["exit_code"])
