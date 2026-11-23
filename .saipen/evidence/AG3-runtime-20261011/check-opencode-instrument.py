"""Check the existing native payload with child-only PATH selection."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "opencode-instrument-control.json"
if OUTPUT.exists():
    raise SystemExit("Existing instrument evidence is immutable")
NATIVE = Path("C:/nodejs/node_modules/opencode-ai/node_modules/opencode-windows-x64/bin/opencode.exe")
SHIM = Path("C:/nodejs/node_modules/opencode-ai/bin/opencode.exe")
INSTALLED = Path(os.environ["USERPROFILE"]) / ".config/opencode/plugins/saipen-guard.js"
SOURCE = ROOT / "extensions/adapters/opencode/saipen-guard.js"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

before = {str(path): digest(path) for path in (NATIVE, SHIM, INSTALLED, SOURCE)}
environment = os.environ.copy()
environment["PATH"] = str(NATIVE.parent) + os.pathsep + environment.get("PATH", "")
command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools",
           "-p", "test_opencode_host_smoke.py"]
run = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                     text=True, encoding="utf-8", errors="replace", timeout=600)
after = {str(path): digest(path) for path in (NATIVE, SHIM, INSTALLED, SOURCE)}
record = {"command": command, "exit_code": run.returncode,
          "stdout": run.stdout, "stderr": run.stderr,
          "instrument_change": "existing native payload directory prepended only in verification child PATH",
          "files_before": before, "files_after": after,
          "files_unchanged": before == after, "host_install_writes": 0,
          "scope": "instrument control; not full-family evidence or host repair"}
OUTPUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"exit_code": run.returncode, "unchanged": before == after,
                  "evidence": str(OUTPUT)}))
print(run.stderr[-4000:])
raise SystemExit(run.returncode if before == after else 1)
