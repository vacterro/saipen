"""Run only the existing relevant regression owners; preserve exact output."""
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent
HOME = CASE.parents[2]
argv = [sys.executable, "-m", "unittest", "test_t1671_lifecycle_authority", "test_t1673_board_only_terminal", "test_t1679_typed_head_quarantine", "-v"]
start = datetime.datetime.now(datetime.timezone.utc).isoformat()
proc = subprocess.run(argv, cwd=HOME / "tools", capture_output=True, text=True, encoding="utf-8", errors="backslashreplace", timeout=600)
output = proc.stdout + proc.stderr
(CASE / "focused-regression.txt").write_text(output, encoding="utf-8")
(CASE / "focused-regression.json").write_text(json.dumps({"argv": argv, "cwd": str(HOME / "tools"), "started_utc": start, "exit_code": proc.returncode, "output_sha256": hashlib.sha256(output.encode()).hexdigest()}, indent=2) + "\n", encoding="utf-8")
print(output[-6500:])
sys.exit(proc.returncode)
