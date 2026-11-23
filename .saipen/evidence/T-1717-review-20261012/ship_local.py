"""Complete the reviewed local no-publish release through the native owner."""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
label = sys.argv[1] if len(sys.argv) > 1 else "local"
output = HERE / ("native-ship-" + label + ".json")
assert not output.exists(), "preserve immutable SHIP evidence"
environment = dict(os.environ)
environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                   GIT_OPTIONAL_LOCKS="0", SAIPEN_CAPABILITY="no-publish")
environment["PATH"] = "C:/nodejs/node_modules/opencode-windows-x64/bin;" + environment["PATH"]
done = subprocess.run([str(ROOT / "bin/saipen.cmd"), "--json", "ship"],
                      cwd=ROOT, env=environment, capture_output=True, timeout=300)
value = json.loads(done.stdout)
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps(value))
assert done.returncode == 0 and value["ok"] and value["code"] == "NO_PUBLISH_MODE", value
