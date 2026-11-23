"""Capture the exact bounded revision inspected by the executing agent."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PATHS = [
    "tools/accept_legacy_debt.py",
    "tools/saipen_engine/accepted_debt.py",
    "tools/saipen_engine/debt_authority.py",
    "tools/saipen_engine/host_authority_broker.py",
    "tools/saipen_engine/host_authority_client.py",
    "tools/saipen_engine/operator_origin.py",
    "tools/saipen_engine/journal.py",
    "tools/test_accepted_debt.py",
    "tools/test_accepted_debt_rebind.py",
    "tools/test_operator_origin_support.py",
    "tools/test_t1851_debt_authority.py",
]
hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in PATHS}
(HERE / "review-scope.json").write_text(
    json.dumps({"ticket": "T-1851", "paths": hashes,
                "reviewer": "executing agent self-audit; no independent person/agent"},
               indent=2, sort_keys=True) + "\n", encoding="utf-8")
diffs = []
for name in PATHS:
    before = HERE / "before" / Path(name).name
    if before.is_file():
        diffs.extend(difflib.unified_diff(
            before.read_text(encoding="utf-8-sig").splitlines(keepends=True),
            (ROOT / name).read_text(encoding="utf-8-sig").splitlines(keepends=True),
            fromfile="T-1851/before/" + name, tofile=name))
(HERE / "owned.diff").write_text("".join(diffs), encoding="utf-8")
print(json.dumps({"paths": len(hashes), "scope": str(HERE / "review-scope.json")}))
