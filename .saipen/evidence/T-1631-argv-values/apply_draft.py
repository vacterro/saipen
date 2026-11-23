"""Apply only the reviewed two-path draft after an exact baseline check."""

import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
SCRATCH = Path(json.loads((HERE / "scratch.json").read_text())["project"])
names = ["tools/saipen.py", "tools/test_t1631_argv_values.py"]
baseline = (HERE / "pre" / names[0]).read_bytes()
if (ROOT / names[0]).read_bytes() != baseline:
    raise SystemExit("production CLI moved after draft; reconcile instead of overwriting")
if (ROOT / names[1]).exists():
    raise SystemExit("new verifier path already exists; do not clobber it")
patch, manifest = [], {}
for name in names:
    before = baseline if name == names[0] else b""
    after = (SCRATCH / name).read_bytes()
    manifest[name] = {"before_sha256": hashlib.sha256(before).hexdigest(),
                      "after_sha256": hashlib.sha256(after).hexdigest()}
    patch.extend(difflib.unified_diff(
        before.decode("utf-8").splitlines(keepends=True),
        after.decode("utf-8").splitlines(keepends=True),
        fromfile="a/" + name, tofile="b/" + name,
    ))
    (ROOT / name).write_bytes(after)
(HERE / "owned.patch").write_text("".join(patch), encoding="utf-8")
(HERE / "scope.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"paths": names, "baseline_held": True}))
