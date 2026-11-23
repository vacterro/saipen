"""Apply only the three CAS-checked A05 paths after preserving exact rollback."""
from __future__ import annotations

import difflib
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.state import parse_state


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


state = parse_state((ROOT / ".saipen/STATE.md").read_text(encoding="utf-8"))
if state.get("task") != "T-1714" or state.get("phase") != "BUILD":
    raise RuntimeError("T-1714 must own BUILD before source application")
output = HERE / "owned-application.json"
if output.exists():
    raise RuntimeError("owned application evidence already exists")
descriptor = json.loads((ROOT / ".saipen/evidence/T-1702-A05/scratch-preparation.json").read_text(encoding="utf-8"))
candidate = Path(descriptor["project"])
paths = ("tools/saipen_engine/reconcile.py", "tools/saipen.py",
         "tools/test_reconcile_history_ledger_blocked.py")
before = {relative: (ROOT / relative).read_bytes() for relative in paths}
after = {relative: (candidate / relative).read_bytes() for relative in paths}
for relative in paths:
    if sha(before[relative]) != descriptor["preimages"][relative]["sha256"]:
        raise RuntimeError("live preimage drift: " + relative)
    if before[relative] == after[relative]:
        raise RuntimeError("candidate owns no delta: " + relative)
    target = HERE / "before" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(before[relative])
patch = ""
for relative in paths:
    patch += "\n".join(difflib.unified_diff(
        before[relative].decode("utf-8").splitlines(), after[relative].decode("utf-8").splitlines(),
        fromfile="before/" + relative, tofile="after/" + relative, lineterm="")) + "\n"
(HERE / "owned-changes.patch").write_text(patch, encoding="utf-8")
for relative in paths:
    if (ROOT / relative).read_bytes() != before[relative]:
        raise RuntimeError("live preimage moved before application: " + relative)
    (ROOT / relative).write_bytes(after[relative])
    if (ROOT / relative).read_bytes() != after[relative]:
        raise RuntimeError("applied bytes failed readback: " + relative)
result = {"ok": True, "work": "T-1714", "candidate": str(candidate),
          "paths": {relative: {"before_sha256": sha(before[relative]),
                               "after_sha256": sha(after[relative]),
                               "preserved_before": (HERE / "before" / relative).relative_to(ROOT).as_posix()}
                    for relative in paths},
          "patch_sha256": sha((HERE / "owned-changes.patch").read_bytes()),
          "limits": "Three attributable paths only; original EOL form preserved. No Git, canonical history, foreign consumer or ACL mutation."}
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
