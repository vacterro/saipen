"""Observe the real post-fix classifier and named legacy-baseline refusal."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine import debt, findings
from saipen_engine.core_unit import tree_fingerprint

ref = "DEBT-000460"
path = root / ".saipen/recovery/conformance/debt" / f"{ref}.json"
raw = path.read_bytes()
report = {
    "ruleset_version": findings.RULESET_VERSION,
    "ruleset_fingerprint": findings.ruleset_fingerprint(),
    "tree_fingerprint": tree_fingerprint(root),
    "legacy_id": ref,
    "legacy_sha256": hashlib.sha256(raw).hexdigest(),
    "handoff": findings.classify(
        "problem", "cross-doc drift [root-file-set] -- unexpected root files: ['T-1446', 'tuple[bool']",
    ),
}
try:
    debt.load_snapshot(root, ref)
except debt.DebtRefusal as exc:
    report["legacy_refusal"] = {"code": exc.code, "detail": str(exc)}
else:
    raise AssertionError("The real legacy snapshot was silently accepted")
assert report["legacy_refusal"]["code"] == "BASELINE_RULESET_CHANGED"
assert report["ruleset_version"] == 2
assert path.read_bytes() == raw
Path(__file__).with_name("current-policy.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
