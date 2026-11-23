"""Preserve the exact final three-file delta without changing production bytes."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
output = HERE / "owned-application-final.json"
if output.exists():
    raise RuntimeError("final ownership evidence is immutable")
initial = json.loads((HERE / "owned-application.json").read_text(encoding="utf-8"))
records = {}
patch = ""
for relative, identity in initial["paths"].items():
    before = (ROOT / identity["preserved_before"]).read_bytes()
    after = (ROOT / relative).read_bytes()
    if hashlib.sha256(before).hexdigest() != identity["before_sha256"]:
        raise RuntimeError("original preimage changed")
    target = HERE / "owned-current-final" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(after)
    records[relative] = {"before_sha256": identity["before_sha256"],
                         "after_sha256": hashlib.sha256(after).hexdigest(),
                         "preserved_before": identity["preserved_before"],
                         "preserved_current": target.relative_to(ROOT).as_posix()}
    patch += "\n".join(difflib.unified_diff(
        before.decode("utf-8").splitlines(), after.decode("utf-8").splitlines(),
        fromfile="before/" + relative, tofile="after/" + relative, lineterm="")) + "\n"
patch_path = HERE / "owned-changes-final.patch"
patch_path.write_text(patch, encoding="utf-8")
output.write_text(json.dumps({"work": "T-1714", "paths": records,
                              "patch_sha256": hashlib.sha256(patch_path.read_bytes()).hexdigest(),
                              "limits": "Original raw preimages and final source bytes; no HEAD-wide attribution or foreign hunk ownership."},
                             indent=2) + "\n", encoding="utf-8")
print(json.dumps({"work": "T-1714", "paths": records, "record": str(output)}))
