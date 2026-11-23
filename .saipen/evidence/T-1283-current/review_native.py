"""Capture the unchanged ticket checks independently after REVIEW entry."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from test_hermetic_env import hermetic_env

for version in ("original", "current"):
    preserved = HERE / ("VERIFY-" + version + ".json")
    if not preserved.exists():
        shutil.copyfile(HERE / (version + ".json"), preserved)

command = [sys.executable, "-B", "-m", "unittest", "-v",
           "test_t1283_lineage_legacy_ingest", "test_conformance_lineage",
           "test_t1519_settled_index"]
with (HERE / "REVIEW-native.stdout").open("wb") as stdout, (HERE / "REVIEW-native.stderr").open("wb") as stderr:
    native = subprocess.run(command, cwd=ROOT / "tools", env=hermetic_env(),
                            stdout=stdout, stderr=stderr, timeout=180)
if native.returncode:
    raise SystemExit(native.returncode)

records = {}
for version in ("original", "current"):
    subprocess.run([sys.executable, "-B", str(HERE / "oracle.py"), version],
                   cwd=ROOT, check=True, timeout=180)
    records[version] = json.loads((HERE / (version + ".json")).read_text(encoding="utf-8"))
assert records["original"]["exit_code"] != 0
assert records["current"]["exit_code"] == 0
assert records["original"]["verifier"] == records["current"]["verifier"]
assert records["original"]["subject"] != records["current"]["subject"]
result = {"native_command": command, "native_exit_code": native.returncode,
          "oracle_verifier": records["current"]["verifier"],
          "original_exit_code": records["original"]["exit_code"],
          "current_exit_code": records["current"]["exit_code"],
          "prior_verify_records_preserved": True}
(HERE / "REVIEW-native.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
