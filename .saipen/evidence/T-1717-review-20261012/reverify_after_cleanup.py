"""Refresh the native DONE-Work receipt requested by post-cleanup conformance."""
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
output = HERE / "native-reverify-after-cleanup.json"
assert not output.exists(), "preserve immutable re-verification result"
environment = dict(os.environ)
environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                   GIT_OPTIONAL_LOCKS="0", SAIPEN_CAPABILITY="no-publish")
environment["PATH"] = "C:/nodejs/node_modules/opencode-windows-x64/bin;" + environment["PATH"]
done = subprocess.run([str(ROOT / "bin/saipen.cmd"), "--json", "work", "reverify", "T-1695"],
                      cwd=ROOT, env=environment, capture_output=True, timeout=300)
value = json.loads(done.stdout)
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps(value))
assert done.returncode == 0 and value["ok"], value
