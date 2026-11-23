"""Register only the two owned empty intent entries; preserve foreign index bytes."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "inventory-registration.json"
if OUTPUT.exists():
    raise SystemExit("Inventory registration already recorded")
owned = {"tools/saipen_engine/regression_execution.py", "tools/test_t1711_regression_execution.py"}

def inventory():
    raw = subprocess.run(["git", "ls-files", "--stage", "-z"], cwd=ROOT,
                         capture_output=True, check=True).stdout
    return {entry.split(b"\t", 1)[1].decode("utf-8"): entry.decode("utf-8")
            for entry in raw.split(b"\0") if entry}

before = inventory()
if any(path in before for path in owned):
    raise SystemExit("Owned new entry already has index state; inspect before modifying")
subprocess.run(["git", "-c", "core.autocrlf=false", "add", "-N", "--", *sorted(owned)],
               cwd=ROOT, check=True)
after = inventory()
foreign = {key: value for key, value in after.items() if key not in owned}
if foreign != before:
    raise SystemExit("Foreign index changed; do not claim inventory isolation")
if any("e69de29bb2d1d6434b8b29ae775ad8c2e48c5391" not in after[path] for path in owned):
    raise SystemExit("Owned inventory is not an empty intent entry")
OUTPUT.write_text(json.dumps({"owned": sorted(owned), "before": before, "after": after,
                              "foreign_entries_identical": True, "code_bytes_staged": False},
                             indent=2) + "\n", encoding="utf-8")
print(json.dumps({"owned": sorted(owned), "foreign_entries_identical": True,
                  "code_bytes_staged": False}))
