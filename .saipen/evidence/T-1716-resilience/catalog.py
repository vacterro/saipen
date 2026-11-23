"""Hash the exact bounded source/test/document scope and original incidents."""
from __future__ import annotations
import ast
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint
from saipen_engine.log import read_history_snapshot

modules = "admission automation capability commands conformance remediation iteration_verdict goal_authority plan journal lock runtime_surface host_integration guard_events regression_execution reconcile operations".split()
tests = "test_guard_admission test_recovery_reachability test_t1494_continuation_authority test_actor_binding_lifecycle test_t1575_parallel_lane test_t1711_regression_execution test_t1712_manifest_runtime test_t1709_audit_starvation test_conformance_repair_boundary test_dependency_resume_liveness test_t1458_queue_reservation test_regression_gate".split()
paths = ["tools/saipen.py"] + [f"tools/saipen_engine/{name}.py" for name in modules]
paths += [f"tools/{name}.py" for name in tests]
paths += [f"saipen/{name}.md" for name in ("CORE", "OPS", "MAINTENANCE", "RUNTIME", "EXECUTION", "STYLE", "COMMANDS")]
paths += [".saipen/intake/active/SRC-215.md", ".saipen/intake/contracts/SRC-215.json",
          ".saipen/evidence/T-1711-admission/REPORT-FINAL-GENERATION.md",
          ".saipen/evidence/T-1714-diagnostics/FINAL-ACCEPTANCE.md",
          ".saipen/evidence/T-1714-diagnostics/verifier-context-comparison.json",
          ".saipen/evidence/T-1714-diagnostics/dependency-reservation-followup.md"]
catalog = {}
for name in paths:
    data = (ROOT / name).read_bytes()
    value = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    if name.endswith(".py"):
        parsed = ast.parse(data.decode("utf-8-sig"))
        value["definitions"] = [{"name": node.name, "line": node.lineno, "end": node.end_lineno}
                                for node in ast.walk(parsed)
                                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    catalog[name] = value
snapshot = read_history_snapshot(ROOT, lean=True)
wanted = {7715, 7716, 7976, 7995, 14412, 14444, 14445, 14447}
events = [event for event in snapshot.events if event["event"] in wanted]
value = {"schema_version": 1, "scope": "bounded Tier 2 direct-source fallback",
         "graph_generation": "2026-09-01T13:16:39Z", "tools_coverage": "excluded",
         "source_fingerprint": tree_fingerprint(ROOT), "files": catalog,
         "original_root_events": events, "original_root_history_hash": snapshot.hash,
         "unobserved": "loaded host generations, original freebuff tool transcript, historical Wintage sidecar bytes"}
output = HERE / "source-catalog.json"
assert not output.exists()
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(catalog), "original_events": len(events),
                  "source_fingerprint": value["source_fingerprint"]}))
