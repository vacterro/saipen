"""Emit only the source-hash-bound UTF-8 delta, preserving inherited edits."""

import difflib
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / ".saipen/evidence/T-1560-utf8-candidate"
manifest = json.loads((DRAFT / "manifest.json").read_text(encoding="utf-8"))
proof = json.loads((DRAFT / "permanent-oracle-green.json").read_text(encoding="utf-8"))
red = json.loads((DRAFT / "permanent-oracle-red.json").read_text(encoding="utf-8"))
test = (DRAFT / "test_subprocess_utf8.py.draft").read_bytes()
if (proof["status"] != "PASS" or red["status"] != "FAIL"
        or proof["oracle_sha256"] != red["oracle_sha256"]
        or hashlib.sha256(test).hexdigest() != proof["oracle_sha256"]):
    raise ValueError("The final fixed oracle lacks a matching FAIL/PASS pair")
changes = []
for record in manifest["files"]:
    relative = record["path"]
    before = (ROOT / relative).read_bytes()
    after = (DRAFT / (relative + ".draft")).read_bytes()
    if hashlib.sha256(before).hexdigest() != record["before_sha256"]:
        raise ValueError(f"Source changed after drafting: {relative}")
    if hashlib.sha256(after).hexdigest() != record["after_sha256"]:
        raise ValueError(f"Candidate changed after drafting: {relative}")
    changes.append((relative, before, after))
test_path = ROOT / "tools/test_subprocess_utf8.py"
if test_path.exists():
    raise ValueError("The new regression path already exists")
lines = ["*** Begin Patch"]
for relative, before, after in changes:
    preserved = DRAFT / "before" / (relative + ".original")
    preserved.parent.mkdir(parents=True, exist_ok=True)
    preserved.write_bytes(before)
    lines.append("*** Update File: " + str(ROOT / relative))
    for line in list(difflib.unified_diff(
        before.decode("utf-8").splitlines(), after.decode("utf-8").splitlines(), lineterm=""
    ))[2:]:
        lines.append("@@" if line.startswith("@@ ") else line)
lines.append("*** Add File: " + str(test_path))
lines.extend("+" + line for line in test.decode("utf-8").splitlines())
lines.append("*** End Patch")
sys.stdout.reconfigure(encoding="utf-8")
print("\n".join(lines))
