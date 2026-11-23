"""Bind the external scratch candidate and prove the in-flight root stayed unchanged."""
import difflib
import hashlib
import json
import re
import shutil
from pathlib import Path

here = Path(__file__).resolve().parent
home = here.parents[2]
binding = json.loads((here / "closure-scratch.json").read_text(encoding="utf-8"))
scratch = Path(binding["scratch_root"]).resolve()
assert not scratch.is_relative_to(home.resolve())
before = here / "closure-intake-before.py"
after = scratch / "tools/saipen_engine/intake.py"
oracle = scratch / "tools/test_src276_closure_outcomes.py"
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert digest(home / "tools/saipen_engine/intake.py") == digest(before)
assert digest(oracle) == digest(here / oracle.name)
scope = json.loads((home / ".saipen/evidence/T-1851-debt-authority/review-scope.json").read_text())
assert all(digest(home / p) == sha for p, sha in scope["paths"].items())
shutil.copy2(after, here / "closure-intake-candidate.py")
(here / "closure-candidate.patch").write_text("".join(difflib.unified_diff(
    before.read_text(encoding="utf-8-sig").splitlines(keepends=True),
    after.read_text(encoding="utf-8-sig").splitlines(keepends=True),
    fromfile="a/tools/saipen_engine/intake.py", tofile="b/tools/saipen_engine/intake.py")),
    encoding="utf-8")
runs = {}
for stage in ("prefix", "postfix", "compatibility", "archive-controls"):
    log = here / f"closure-scratch-{stage}.log"
    if log.exists():
        text = log.read_text(encoding="utf-8-sig")
        summary = re.search(r"Ran (\d+) tests? in ([\d.]+)s", text)
        runs[stage] = {"log_sha256": digest(log),
                       "ran": int(summary[1]) if summary else None,
                       "summary": text.splitlines()[-1] if text.splitlines() else None}
proof = {"scope": "next-Work scratch preparation only; no native lifecycle proof",
         "before_sha256": digest(before), "after_sha256": digest(after),
         "oracle_sha256": digest(oracle), "runs": runs,
         "root_intake_unchanged": True, "all_11_T1851_reviewed_files_unchanged": True}
(here / "closure-scratch-proof.json").write_text(json.dumps(proof, indent=2) + "\n",
                                                encoding="utf-8")
print(json.dumps(proof))
