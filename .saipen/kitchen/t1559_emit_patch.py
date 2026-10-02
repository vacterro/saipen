"""Emit only the already measured, hash-bound STYLE owner-text restoration."""
import difflib
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="strict")
ROOT = Path(__file__).resolve().parents[2]
out = ROOT / ".saipen/evidence/T-1559-style-candidate"
manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
mutations = json.loads((out / "mutation-controls.json").read_text(encoding="utf-8"))
checks = mutations["controls"]
if [check["verdict"] for check in checks] != ["FAIL", "PASS"]:
    raise RuntimeError("mutation oracle has no red/green pair")
if hashlib.sha256((ROOT / "tools/audit_checks.py").read_bytes()).hexdigest() != mutations["oracle_sha256"]:
    raise RuntimeError("mutation verifier moved after controls")
target = ROOT / manifest["path"]
before = target.read_bytes()
after = (out / "STYLE.md").read_bytes()
if hashlib.sha256(before).hexdigest() != manifest["before_sha256"]:
    raise RuntimeError("live STYLE moved after preparation")
if hashlib.sha256(after).hexdigest() != manifest["after_sha256"]:
    raise RuntimeError("candidate STYLE moved after controls")
if not manifest["measurable_contract_unchanged"] or manifest["normalized_byte_delta"] > 0:
    raise RuntimeError("unexpected contract or prose budget growth")
(out / "STYLE.md.before").write_bytes(before)
diff = list(difflib.unified_diff(before.decode().splitlines(), after.decode().splitlines(), n=3))
print("*** Begin Patch\n*** Update File: saipen/STYLE.md")
for line in diff[2:]:
    print("@@" if line.startswith("@@") else line)
print("*** End Patch")
