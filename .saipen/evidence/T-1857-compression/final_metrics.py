"""Read-only frozen-source metrics; writes evidence only, grants no verdict."""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import protocol_budget

BRANCHES = (ast.If, ast.IfExp, ast.For, ast.While, ast.ExceptHandler, ast.Match)
BASELINE = {
    "cold": 27643,
    "command_resolution": 56160,
    "ordinary_continue": 34570,
    "ordinary_phase": 40943,
    "ship_improve": 55625,
}


def metrics(text: str) -> dict:
    tree = ast.parse(text)
    return {
        "lf_bytes": len(text.encode("utf-8")),
        "lines": len(text.splitlines()),
        "functions": sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                         for n in ast.walk(tree)),
        "branch_sites": sum(isinstance(n, BRANCHES) for n in ast.walk(tree)),
    }


manifest = json.loads((HERE / "owned-files.json").read_text(encoding="utf-8"))
rows = []
drift = []
for entry in manifest["files"]:
    relative = entry["path"]
    current = (ROOT / relative).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if hashlib.sha256(current.encode()).hexdigest() != entry["after_sha256"]:
        drift.append(relative)
    if not relative.endswith(".py"):
        continue
    before = entry["before_artifact"]
    original = ((HERE / "before" / before).read_text(encoding="utf-8-sig")
                .replace("\r\n", "\n")) if before else ""
    if before and hashlib.sha256(original.encode()).hexdigest() != entry["before_sha256"]:
        raise ValueError(f"Changed Python before-image: {relative}")
    rows.append({"path": relative, "kind": "test" if relative.startswith("tools/test_")
                 else "product", "before": metrics(original), "after": metrics(current)})

totals = {}
for kind in ("product", "test"):
    selection = [r for r in rows if r["kind"] == kind]
    totals[kind] = {"files": len(selection)}
    for stage in ("before", "after"):
        totals[kind][stage] = {key: sum(r[stage][key] for r in selection)
                               for key in ("lf_bytes", "lines", "functions", "branch_sites")}

loaded = protocol_budget.load_profiles()
profiles = {
    name: {"before": before, "after": loaded[name],
           "reduction_percent": round((before-loaded[name])*100/before, 4)}
    for name, before in BASELINE.items()
}
result = {
    "observed_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "Campaign deltas against captured working before-images; no HEAD ownership claim",
    "branch_definition": "If, IfExp, For, While, ExceptHandler, Match AST nodes; not cyclomatic complexity",
    "owned_source_drift": drift,
    "totals": totals,
    "files": rows,
    "context_profiles_lf_bytes": profiles,
    "budgets": loaded["budgets"],
    "limitations": [
        "New diagnostic behavior adds code; no net Python-size or global speed reduction is claimed.",
        "A conditional command-table move reduces loaded context, not historical storage.",
        "Evidence completion, native trust, Source acceptance and publication remain independent gates.",
    ],
}
(HERE / "frozen-metrics.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
print(json.dumps({k: result[k] for k in ("observed_utc", "owned_source_drift", "totals",
                                        "context_profiles_lf_bytes", "budgets")}, indent=2))
if drift:
    raise SystemExit(1)
