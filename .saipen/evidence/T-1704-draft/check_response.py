"""Check the evidence-linked compact handback against actual canonical status."""
import json
import subprocess
import sys
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
argv = [sys.executable, str(root / "tools/saipen.py"), "response", "check", "--stdin",
        "--classify", "--auto-eligibility", "--project-root", str(root), "--json"]
result = subprocess.run(argv, cwd=root, input=(evidence / "final-response.txt").read_text(encoding="utf-8"),
                        capture_output=True, text=True, encoding="utf-8")
try:
    output = json.loads(result.stdout)
except ValueError:
    output = result.stdout
record = {"argv": argv, "exit_code": result.returncode, "stdout": output, "stderr": result.stderr}
(evidence / "final-response-check.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, indent=2))
raise SystemExit(result.returncode)
