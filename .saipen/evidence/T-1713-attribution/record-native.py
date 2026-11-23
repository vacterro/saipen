"""Keep the actual native core result for each T-1713 phase."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.state import parse_state

stage = sys.argv[1]
state = parse_state((ROOT / ".saipen/STATE.md").read_text(encoding="utf-8"))
if stage not in {"verify", "review"} or state.get("task") != "T-1713" or state.get("phase") != stage.upper():
    raise RuntimeError("T-1713 does not own this native gate phase")
output = HERE / ("native-" + stage + "-current.json")
if output.exists():
    raise RuntimeError("existing native phase evidence is immutable")
command = [sys.executable, "-B", "tools/validate.py", "--gate", "core"]
run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
result = {"stage": stage, "command": command, "exit_code": run.returncode,
          "stdout": run.stdout.decode("utf-8", errors="replace"),
          "stderr": run.stderr.decode("utf-8", errors="replace"),
          "stdout_sha256": hashlib.sha256(run.stdout).hexdigest(),
          "stderr_sha256": hashlib.sha256(run.stderr).hexdigest()}
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"stage": stage, "exit_code": run.returncode, "record": str(output)}))
print(result["stdout"][-950:])
sys.exit(run.returncode)
