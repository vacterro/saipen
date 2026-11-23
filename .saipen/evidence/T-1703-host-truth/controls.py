"""Existing B01 controls plus deliberate in-memory lies, never production edits."""
import ast
import contextlib
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PREFIX = sys.argv[1]
sys.path.insert(0, str(ROOT / "tools"))
methods = {
    "test_t1624_host_integration": {
        "test_each_state_is_reached_from_the_facts_that_define_it",
        "test_a_hook_that_exists_is_not_a_healthy_host",
        "test_a_health_record_of_another_hook_file_is_not_evidence_about_this_host",
        "test_a_marker_or_a_declaration_is_not_mechanical_admission",
        "test_no_registered_host_has_an_undeclared_cell",
        "test_no_host_claims_more_than_its_files_can_do",
        "test_the_cross_host_asymmetry_is_a_recorded_capability_difference",
    },
    "test_guard_hostile_matrix": {
        "test_current_artifact_without_host_health_is_unknown",
        "test_16_kiro_capability_is_true_and_enforcement_is_a_gap",
        "test_17_gemini_capability_is_true_and_enforcement_is_advisory",
        "test_18_missing_adapter_cannot_report_effective_blocking",
        "test_19_stale_adapter_cannot_report_effective_blocking",
    },
}
targets = {}
sources = {}
for module, names in methods.items():
    path = ROOT / "tools" / (module + ".py")
    sources[module] = hashlib.sha256(path.read_bytes()).hexdigest()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name in names:
                    targets[child.name] = module + "." + node.name + "." + child.name
    importlib.import_module(module)
assert len(targets) == sum(len(names) for names in methods.values()) == 12


def run(label, names, patch=None, expected_failures=0):
    stream = io.StringIO()
    context = patch or contextlib.nullcontext()
    with context:
        suite = unittest.defaultTestLoader.loadTestsFromNames([targets[name] for name in names])
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    raw = stream.getvalue()
    (OUT / (PREFIX + "-" + label + ".txt")).write_text(raw, encoding="utf-8")
    assert result.testsRun == len(names) and not result.errors, raw
    assert len(result.failures) == expected_failures, raw
    return {"label": label, "ran": result.testsRun,
            "failures": [test.id() for test, trace in result.failures], "errors": len(result.errors)}


all_names = sorted(targets)
records = [run("good", all_names)]
for repetition in range(2):
    records.append(run("bad-tool-" + str(repetition), [
        "test_current_artifact_without_host_health_is_unknown",
        "test_18_missing_adapter_cannot_report_effective_blocking",
        "test_19_stale_adapter_cannot_report_effective_blocking"],
        mock.patch("test_guard_hostile_matrix.effective_strength",
                   return_value={"effective": "BLOCKING", "current": True}), 3))
    records.append(run("bad-admission-" + str(repetition), [
        "test_a_marker_or_a_declaration_is_not_mechanical_admission"],
        mock.patch("saipen_engine.host_integration.effective_admission", return_value="MECHANICAL"), 1))
records.append(run("restored-good", all_names))
assert records[1]["failures"] == records[3]["failures"]
assert records[2]["failures"] == records[4]["failures"]
assert all(hashlib.sha256((ROOT / "tools" / (name + ".py")).read_bytes()).hexdigest() == digest
           for name, digest in sources.items())
(OUT / (PREFIX + "-controls.json")).write_text(json.dumps({"records": records,
    "existing_oracle_sha256": sources, "production_edits": 0,
    "controls": "Known-bad in-memory implementation lies; not a bug-fix regression pair."}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"good": 12, "restored_good": 12, "bad_tool": 3, "bad_admission": 1,
                  "red_names_repeat": True, "production_edits": 0}))
