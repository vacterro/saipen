"""Run one unchanged oracle against preserved pre-fix and fixed subjects."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCRATCH = Path("V:/_TEMP_/saipen-t1712-runtime-20261011").resolve()
SUBJECTS = ["tools/saipen_engine/audit_manifest.py", "tools/saipen_engine/paths.py",
            "tools/saipen_engine/host_bootstrap.py", "tools/saipen_engine/reconcile.py",
            "tools/saipen.py", "tools/saipen_engine/init_project.py"]
fixed = HERE / "fixed-subject-files"
if fixed.exists() or (HERE / "red-final.json").exists():
    raise SystemExit("Final paired evidence already exists")
for rel in SUBJECTS:
    target = fixed / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRATCH / rel, target)
try:
    for rel in SUBJECTS:
        shutil.copy2(ROOT / rel, SCRATCH / rel)
    subprocess.run([sys.executable, "-B", str(HERE / "control.py"), "red-final", str(SCRATCH)],
                   check=True)
finally:
    for rel in SUBJECTS:
        shutil.copy2(fixed / rel, SCRATCH / rel)
subprocess.run([sys.executable, "-B", str(HERE / "control.py"), "green-final", str(SCRATCH)],
               check=True)
red = json.loads((HERE / "red-final.json").read_text(encoding="utf-8"))
green = json.loads((HERE / "green-final.json").read_text(encoding="utf-8"))
if red["exit_code"] == 0 or green["exit_code"] != 0 or red["verifier"] != green["verifier"]:
    raise SystemExit("Final unchanged-oracle pair is not admissible")
print("Frozen oracle pair: pre-fix FAIL / corrected PASS")
