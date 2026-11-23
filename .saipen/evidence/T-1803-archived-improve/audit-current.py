"""Read current mission bytes; write evidence only, never consumer state."""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONSUMER = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def symbols(raw):
    tree = ast.parse(raw.decode("utf-8-sig"))
    return {
        node.name: ast.dump(node, include_attributes=False)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def main():
    baseline = json.loads((HERE / "baseline-observation.json").read_text(encoding="utf-8"))
    expected = baseline["protected_before"]
    observed = {
        name: sha((CONSUMER / name).read_bytes()) if (CONSUMER / name).is_file() else "ABSENT"
        for name in expected
    }
    if observed != expected:
        raise RuntimeError("Live consumer protected history differs from the original observation")
    manifest = json.loads((HERE / "engine-before/manifest.json").read_text(encoding="utf-8"))
    changes = {}
    patches = []
    for name, digest in manifest.items():
        before = (HERE / "engine-before" / name).read_bytes()
        if sha(before) != digest:
            raise RuntimeError("Preserved preimage changed: " + name)
        current = (ROOT / name).read_bytes()
        row = {"before_sha256": digest, "current_sha256": sha(current), "changed": current != before}
        if name.endswith(".py"):
            old, new = symbols(before), symbols(current)
            row["symbols_added"] = sorted(new.keys() - old.keys())
            row["symbols_removed"] = sorted(old.keys() - new.keys())
            row["symbols_modified"] = sorted(key for key in old.keys() & new.keys() if old[key] != new[key])
        changes[name] = row
        if current != before:
            patches.extend(difflib.unified_diff(
                before.decode("utf-8-sig").replace("\r\n", "\n").splitlines(keepends=True),
                current.decode("utf-8-sig").replace("\r\n", "\n").splitlines(keepends=True),
                fromfile="preimage/" + name, tofile="current/" + name,
            ))
    added = ROOT / "tools/saipen_engine/improve_retrospective.py"
    tests = ROOT / "tools/test_t1803_archived_improve.py"
    test_tree = ast.parse(tests.read_text(encoding="utf-8"))
    test_names = sorted(node.name for node in ast.walk(test_tree)
                        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
    original_oracle = HERE / "schema-before/tools/test_t1803_archived_improve.py"
    old_methods = {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.walk(ast.parse(original_oracle.read_text(encoding="utf-8-sig")))
        if isinstance(node, ast.FunctionDef)
    }
    current_methods = {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.walk(test_tree) if isinstance(node, ast.FunctionDef)
    }
    removed_methods = sorted(old_methods.keys() - current_methods.keys())
    changed_methods = sorted(name for name in old_methods.keys() & current_methods.keys()
                             if old_methods[name] != current_methods[name])
    if removed_methods or changed_methods:
        raise RuntimeError("The earlier oracle's assertions/helpers changed")
    body = ROOT / ".saipen/intake/active/SRC-261.md"
    meta = json.loads(body.with_suffix(".meta.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / ".saipen/intake/contracts/SRC-261.json").read_text(encoding="utf-8"))
    source_digest = sha(body.read_bytes())
    if source_digest != meta["source_sha256"] or source_digest != contract["source_sha256"]:
        raise RuntimeError("Current Source/Contract integrity failed")
    result = {
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "engine_root": str(ROOT),
        "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip(),
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "consumer_root": str(CONSUMER),
        "consumer_lineage": baseline["consumer_lineage"],
        "consumer_protected_bytes_unchanged": observed == expected,
        "consumer_protected_sha256": observed,
        "consumer_t311_record": next(line for line in (CONSUMER / ".saipen/BOARD.md").read_text(encoding="utf-8-sig").splitlines()
                                     if "T-311 " in line),
        "original_history_cases": baseline["cycles"],
        "source_sha256": source_digest,
        "source_provenance": meta["request_provenance"]["witness"],
        "actionable_clauses": len(contract["clauses"]),
        "mission_preimage_comparison": changes,
        "new_module": {"path": str(added.relative_to(ROOT)), "sha256": sha(added.read_bytes()),
                       "symbols": sorted(symbols(added.read_bytes()))},
        "focused_tests": {"path": str(tests.relative_to(ROOT)), "sha256": sha(tests.read_bytes()),
                          "count": len(test_names), "names": test_names},
        "oracle_expansion": {"removed": removed_methods, "changed": changed_methods,
                             "added": sorted(current_methods.keys() - old_methods.keys()),
                             "reason": "Concrete introduced malformed JSON event/proof-map failure; six RED controls before the implementation-only correction"},
        "graph_limitation": "Tier 2; saipen generation 2026-09-01T13:16:39Z excludes tools/. Direct current source and executed tests supply engine evidence.",
    }
    (HERE / "current-audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (HERE / "mission-only.diff").write_text("".join(patches), encoding="utf-8", newline="\n")
    print(json.dumps({"consumer_unchanged": True, "head": result["head"], "version": result["version"],
                      "clauses": result["actionable_clauses"], "focused_tests": len(test_names),
                      "changes": changes}, indent=2))


if __name__ == "__main__":
    main()
