"""Execute one declared gate with managed child cleanup and raw captured streams."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint
from saipen_engine.process_tree import run
from saipen_engine.state import parse_state

label, timeout, directory, *command = sys.argv[1:]
if not re.fullmatch(r"[a-z0-9-]+", label) or not command:
    raise ValueError("a bounded label and argv are required")
output = HERE / (label + ".json")
if output.exists():
    raise RuntimeError("gate evidence already exists")
state = parse_state((ROOT / ".saipen/STATE.md").read_text(encoding="utf-8"))
if state.get("task") != "T-1716" or state.get("phase") not in {"SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP"}:
    raise RuntimeError("T-1716 does not own the gate phase")
baseline = tree_fingerprint(ROOT)
environment = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
environment.update(SAIPEN_CAPABILITY="no-publish", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
started = time.monotonic()
result = run(command, cwd=ROOT / directory, env=environment,
             capture_output=True, timeout=int(timeout))
if tree_fingerprint(ROOT) != baseline:
    raise RuntimeError("gate changed the source generation")
value = {"label": label, "phase": state["phase"], "command": command,
         "cwd": str(ROOT / directory), "exit_code": result.returncode,
         "duration_s": round(time.monotonic() - started, 3), "fingerprint": baseline,
         "stdout": result.stdout.decode("utf-8", errors="replace"),
         "stderr": result.stderr.decode("utf-8", errors="replace"),
         "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
         "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
         "source_unchanged": True, "cleanup": "repository process_tree.run owns descendants"}
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
(HERE / (label + ".stdout.bin")).write_bytes(result.stdout)
(HERE / (label + ".stderr.bin")).write_bytes(result.stderr)
print(json.dumps({key: value[key] for key in ("label", "phase", "exit_code", "duration_s", "fingerprint")}))
print((value["stdout"] + value["stderr"])[-2000:])
sys.exit(result.returncode)
