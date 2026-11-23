"""Reproducible campaign measurements; these artifacts grant no authority."""
from __future__ import annotations
import ast
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import board
import protocol_budget

FILES = [
    "tools/saipen_engine/board.py", "tools/saipen_engine/router.py",
    "tools/saipen_engine/audit_inbox.py", "tools/saipen_engine/response_surface.py",
    "tools/saipen_engine/automation.py", "tools/saipen_engine/goal_authority.py",
    "tools/saipen_engine/operations.py", "tools/saipen.py",
]
BRANCHES = (ast.If, ast.IfExp, ast.For, ast.While, ast.ExceptHandler, ast.Match)

def source_metrics(path):
    data = path.read_bytes().replace(b"\r\n", b"\n")
    tree = ast.parse(data.decode("utf-8-sig"))
    return {"lf_bytes": len(data), "physical_lines": len(data.splitlines()),
            "functions": sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree)),
            "branch_sites": sum(isinstance(n, BRANCHES) for n in ast.walk(tree))}

def samples(fn, count=50):
    readings = []
    for _ in range(count):
        start = time.perf_counter_ns()
        fn()
        readings.append((time.perf_counter_ns()-start)/1e6)
    return {"samples": count, "median_ms": statistics.median(readings),
            "min_ms": min(readings), "max_ms": max(readings)}

def main():
    changes = {}
    for name in FILES:
        old = HERE / "before" / name.replace("/", "__")
        changes[name] = {"before": source_metrics(old), "after": source_metrics(ROOT / name)}
    spec = importlib.util.spec_from_file_location(
        "saipen_engine._compression_before_board", HERE / "before/tools__saipen_engine__board.py")
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    current = board.parse_board((ROOT / ".saipen/BOARD.md").read_text(encoding="utf-8"))
    fixture = {tid: item for tid, item in current["tickets"].items() if tid not in {"T-1857", "T-1858"}}
    before = previous.classify_idle_work(fixture)
    after = board.classify_idle_work(fixture)
    projection = board.project_blockers(fixture)
    (HERE / "blocker-projection.json").write_text(json.dumps(projection, indent=2)+"\n", encoding="utf-8")
    result = {
        "measurement": "scoped engineering measurements, not lifecycle or native-host acceptance",
        "source_files": changes,
        "branch_site_definition": "If, IfExp, For, While, ExceptHandler, Match AST nodes; not formal cyclomatic complexity",
        "idle_fixture": {"origin": "current BOARD with campaign-only T-1857/T-1858 excluded IN MEMORY",
                         "counts": {s: sum(t["section"] == s for t in fixture.values()) for s in board.REQUIRED_HEADINGS},
                         "before": {k: before[k] for k in ("disposition","next_exact_action","all_requirements_complete")},
                         "after": {k: after[k] for k in ("disposition","next_exact_action","all_requirements_complete")},
                         "primary_blocker": after.get("primary_blocker"),
                         "before_timing": samples(lambda: previous.classify_idle_work(fixture)),
                         "after_timing": samples(lambda: board.classify_idle_work(fixture))},
        "context": protocol_budget.load_profiles(),
    }
    (HERE / "measurements.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"fixture": result["idle_fixture"], "profile_bytes":
        {k: result["context"][k] for k in result["context"]["budgets"]}}, indent=2))

if __name__ == "__main__":
    main()

