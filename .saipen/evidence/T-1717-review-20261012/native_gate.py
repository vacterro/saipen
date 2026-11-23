"""Capture one current native core verdict without overwriting prior evidence."""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
label = sys.argv[1]
output = HERE / ("native-core-" + label + ".json")
assert not output.exists(), "preserve existing native evidence"
environment = dict(os.environ)
environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                   GIT_OPTIONAL_LOCKS="0", SAIPEN_CAPABILITY="no-publish")
environment["PATH"] = "C:/nodejs/node_modules/opencode-windows-x64/bin;" + environment["PATH"]
done = subprocess.run([str(ROOT / "bin/saipen.cmd"), "--json", "validate"],
                      cwd=ROOT, env=environment, capture_output=True, timeout=300)
value = json.loads(done.stdout)
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"label": label, "exit_code": done.returncode, "ok": value.get("ok"),
                  "code": value.get("code"), "conformance": value.get("conformance_status", {}).get("status"),
                  "findings": value.get("conformance_status", {}).get("receipt", {}).get("blocking_findings")}))
assert done.returncode == 0 and value["ok"] and value["conformance_status"]["status"] == "CURRENT_PASS", value
