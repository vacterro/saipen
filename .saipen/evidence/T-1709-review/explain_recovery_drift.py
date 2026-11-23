"""Compare current external files with preserved manifests, without writing them."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = ROOT / ".saipen/evidence/AUDAPACK-recovery-20261010"
sys.path.insert(0, str(PRIOR))
from preflight import ORIGINAL, RECOVERY, inventory

prior = json.loads((PRIOR / "phase0.json").read_text(encoding="utf-8"))
baseline = prior["complete_original"]
current = inventory(ORIGINAL)
recovery = inventory(RECOVERY)
old_files, new_files = baseline["files"], current["files"]
added = sorted(new_files.keys() - old_files.keys())
missing = sorted(old_files.keys() - new_files.keys())
changed = [rel for rel in sorted(old_files.keys() & new_files.keys())
           if (old_files[rel]["sha256"], old_files[rel]["bytes"])
           != (new_files[rel]["sha256"], new_files[rel]["bytes"])]
result = {"original_baseline_count": baseline["file_count"],
          "original_current_count": current["file_count"],
          "added": added, "missing": missing, "changed": changed,
          "original_risks": current["risks"], "recovery_risks": recovery["risks"],
          "baseline_risks": baseline["risks"], "mutations": []}
output = HERE / "recovery-drift.json"
with output.open("x", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2)
    handle.write("\n")
summary = {key: (value[:35] if isinstance(value, list) else value)
           for key, value in result.items()}
summary["full_evidence"] = str(output)
print(json.dumps(summary, indent=2))
