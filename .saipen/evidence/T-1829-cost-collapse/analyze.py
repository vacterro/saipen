"""Read-only historical baseline. No suite, imports of tests, or truth decisions."""
import ast
import collections
import datetime as dt
import json
import math
import os
import statistics
from pathlib import Path

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent


def percentile(values, percent):
    return sorted(values)[max(0, math.ceil(len(values) * percent / 100) - 1)] if values else None


def summarize(rows):
    durations = [r["duration_s"] for r in rows if isinstance(r.get("duration_s"), (int, float))]
    groups = collections.defaultdict(list)
    for row in rows:
        if row.get("fingerprint"):
            groups[row["fingerprint"]].append(row)
    repeated = [r for group in groups.values() for r in group[1:]]
    repeated_pass = []
    for group in groups.values():
        passed = [r for r in group if r.get("verdict") == "PASS"]
        repeated_pass.extend(passed[1:])
    modules = collections.defaultdict(list)
    for row in rows:
        for name, seconds in (row.get("module_durations_s") or {}).items():
            if isinstance(seconds, (int, float)):
                modules[name].append(seconds)
    return {
        "execution_records": len(rows), "durations_present": len(durations),
        "aggregate_recorded_run_wall_s": round(sum(durations), 3),
        "median_recorded_run_wall_s": statistics.median(durations) if durations else None,
        "p95_recorded_run_wall_s": percentile(durations, 95),
        "distinct_source_fingerprints": len(groups),
        "additional_same_fingerprint_records": len(repeated),
        "additional_same_fingerprint_pass_records": len(repeated_pass),
        "additional_same_fingerprint_pass_run_s": round(sum(r.get("duration_s") or 0 for r in repeated_pass), 3),
        "by_status": dict(collections.Counter(r.get("status", "UNKNOWN") for r in rows)),
        "by_jobs": {str(jobs): {"records": len(selected),
            "median_run_wall_s": statistics.median([r["duration_s"] for r in selected])}
            for jobs in sorted({int(r.get("jobs") or 1) for r in rows})
            if (selected := [r for r in rows if int(r.get("jobs") or 1) == jobs
                             and isinstance(r.get("duration_s"), (int, float))])},
        "runs_with_stage_timings": sum(bool(r.get("timings")) for r in rows),
        "runs_with_environment_identity": sum(bool(r.get("environment_identity")) for r in rows),
        "runs_with_module_timings": sum(bool(r.get("module_durations_s")) for r in rows),
        "module_process_time": sorted([
            {"module": name, "samples": len(values), "sum_process_s": round(sum(values), 3),
             "median_process_s": round(statistics.median(values), 3), "max_process_s": max(values)}
            for name, values in modules.items()
        ], key=lambda r: -r["sum_process_s"]),
        "recent": [{k: r.get(k) for k in ("path", "fingerprint", "finished_utc", "ran", "jobs", "status", "verdict", "duration_s")}
                   for r in rows[-12:]],
        "interpretation": "Repeated fingerprints are candidates, not proven redundant compatible runs. Summed run durations and summed module process durations are NOT operator elapsed time.",
    }


def load_records(directory):
    rows, errors = [], []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                rows.append({**data, "path": path.relative_to(ROOT).as_posix()})
            else:
                errors.append({"path": str(path), "error": "not an object"})
        except (OSError, ValueError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
    return sorted(rows, key=lambda r: (r.get("finished_utc") or r["path"], r["path"])), errors


def filesystem(scope):
    count = total = errors = 0
    top = collections.defaultdict(lambda: {"files": 0, "bytes": 0})
    for directory, _dirs, files in os.walk(scope):
        for name in files:
            path = Path(directory) / name
            try:
                size = path.stat().st_size
            except OSError:
                errors += 1
                continue
            count += 1
            total += size
            relative = path.relative_to(scope)
            category = relative.parts[0]
            top[category]["files"] += 1
            top[category]["bytes"] += size
    return {"files": count, "bytes": total, "stat_errors": errors,
            "by_top_level": dict(sorted(top.items(), key=lambda item: -item[1]["bytes"]))}


def dependency_evidence():
    relatives = ["core_unit.py", "core_unit_shard.py", "test_runner.py", "operations.py",
                 "focused_unit.py", "release.py", "efficiency.py", "telemetry.py"]
    graph = []
    for relative in relatives:
        path = ROOT / "tools/saipen_engine" / relative
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        functions = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[node.name] = {"line": node.lineno, "calls": sorted({
                    ast.unparse(call.func) for call in ast.walk(node) if isinstance(call, ast.Call)
                })}
        graph.append({"path": path.relative_to(ROOT).as_posix(), "functions": functions})
    return {"tier": "Verify/source fallback", "mcp_project": None, "mcp_generation": None,
            "coverage": "MCP graph and coverage tools unavailable; exact listed source files parsed. Static calls do not prove dynamic dependency completeness.",
            "files": graph}


def main():
    full, errors = load_records(ROOT / ".saipen/evidence/core-unit")
    focused, focused_errors = load_records(ROOT / ".saipen/evidence/focused-unit")
    baseline = {
        "schema": 1, "advisory": True, "observed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "classification": "historical records plus direct filesystem inventory; no benchmark executed",
        "core_unit": summarize(full), "focused_unit": summarize(focused),
        "saipen_tree": filesystem(ROOT / ".saipen"),
        "top_level_test_modules": len(list((ROOT / "tools").glob("test_*.py"))),
        "read_errors": errors + focused_errors,
        "missing_measurements": {name: None for name in (
            "copy_wall_s", "hash_wall_s", "discovery_wall_s", "python_startup_s",
            "canonical_validation_s", "lifecycle_gate_elapsed_s", "forced_fresh_reasons",
            "actual_implementation_s", "operator_wait_wall_s", "verification_share",
            "flake_attribution", "cache_hit_rate", "escaped_regressions_by_tier")},
        "operator_observation": {"verification_share_percent": 98, "independently_verified": False},
    }
    (OUT / "baseline.json").write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    (OUT / "dependency-evidence.json").write_text(json.dumps(dependency_evidence(), indent=2) + "\n", encoding="utf-8")
    core = baseline["core_unit"]
    text = ["# Historical verification baseline", "", baseline["classification"], "",
            f"- Full execution records: {core['execution_records']}",
            f"- Aggregate recorded run wall time: {core['aggregate_recorded_run_wall_s'] / 3600:.3f} h (sum, not operator elapsed)",
            f"- Median / P95 run: {core['median_recorded_run_wall_s']} / {core['p95_recorded_run_wall_s']} s",
            f"- Distinct tested source fingerprints: {core['distinct_source_fingerprints']}",
            f"- Extra same-fingerprint executions: {core['additional_same_fingerprint_records']}",
            f"- Extra same-fingerprint PASS executions: {core['additional_same_fingerprint_pass_records']}",
            f"- Their recorded run time: {core['additional_same_fingerprint_pass_run_s'] / 3600:.3f} h",
            f"- Records with environment identity / stage timing: {core['runs_with_environment_identity']} / {core['runs_with_stage_timings']}",
            f"- .saipen inventory: {baseline['saipen_tree']['files']} files, {baseline['saipen_tree']['bytes'] / 1024**2:.3f} MiB",
            f"- Top-level test modules: {baseline['top_level_test_modules']}", "",
            "Same source alone cannot prove environmental compatibility. Duplicates are investigation candidates.",
            "Historical module totals below are summed process time, not parallel wall time.", "",
            "| Module | Samples | Median process s | Sum process s |", "|---|---:|---:|---:|"]
    for row in core["module_process_time"][:15]:
        text.append(f"| {row['module']} | {row['samples']} | {row['median_process_s']} | {row['sum_process_s']} |")
    text += ["", "## Missing observations", "",
             "No historical stage timers or environment identity exist in these records. Copy/hash/discovery/startup/validation/gate wall time, fresh-run cause, implementation time, flake attribution and true verification share are unknown, never zero.",
             "The operator's 98% observation remains unverified. No throughput target is claimed achieved.", "",
             "## Ranked mechanisms to investigate", "",
             "1. Repeated full executions / per-ticket boundary frequency: candidate upper bound is the repeated PASS hours above; compatibility must be proven before savings are claimed.",
             "2. Whole-family execution for narrow iterations: prior focused work changes scope; its timings are not an equivalent-workload speedup. Inspect formal lifecycle safety before treating it as sufficient.",
             "3. Serial full runs versus existing shards: historical job distributions are available, but workload/host/environment equivalence is not proved.",
             "4. High-cost modules above: profile mechanism before editing assertions or fixtures.",
             "5. Full .saipen copies, repeated shard copies, source hashes and discovery: large inventory is observed; duration and preventable share still need direct timers.",
             "6. Repeated lifecycle/status gates: existing KPI is not elapsed time. Instrument one representative gate before generalizing.", "",
             "## Dependency evidence", "",
             "MCP graph/coverage tools are unavailable in this host. dependency-evidence.json records exact static source fallback and limitations; dynamic completeness is not claimed.", ""]
    (OUT / "baseline.md").write_text("\n".join(text), encoding="utf-8")
    print(json.dumps({"full_records": core["execution_records"], "hours": round(core["aggregate_recorded_run_wall_s"] / 3600, 3),
                      "repeated_pass": core["additional_same_fingerprint_pass_records"],
                      "repeated_pass_hours": round(core["additional_same_fingerprint_pass_run_s"] / 3600, 3),
                      "saipen_files": baseline["saipen_tree"]["files"], "saipen_mib": round(baseline["saipen_tree"]["bytes"] / 1024**2, 2),
                      "top_modules": core["module_process_time"][:5], "errors": len(baseline["read_errors"])}))


if __name__ == "__main__":
    main()
