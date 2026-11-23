"""Declare the actual complete Python/protocol dependencies, excluding caches."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
output = HERE / "regression-contract.json"
if output.exists():
    raise RuntimeError("execution contract already exists")
oracle = ["tools/test_reconcile_history_ledger_blocked.py", "tools/test_regression_gate.py",
          "tools/test_log_tail_quarantine.py", "tools/test_hermetic_env.py", "tools/test_fixture_support.py"]
subjects = ["tools/saipen_engine/reconcile.py", "tools/saipen.py"]
context = [path.relative_to(ROOT).as_posix() for path in (ROOT / "tools/saipen_engine").glob("*.py")]
context.extend(path.relative_to(ROOT).as_posix() for path in (ROOT / "tools").glob("*.py")
               if not path.name.startswith("test_"))
context.extend(oracle)
context.extend(["saipen", "extensions/adapters/registry.json", "extensions/schemas", "extensions/subs/PROTOCOL.md",
                "VERSION", "README.md", "CHANGELOG.md", ".gitignore", ".gitattributes"])
context = sorted(set(context))
if len(context) > 256:
    raise RuntimeError("dependency path list exceeds the supported bound")
contract = {"schema": 1, "command": ["{python}", "-B", "tools/test_reconcile_history_ledger_blocked.py"],
            "format": "unittest", "context": context, "oracle_files": oracle,
            "subject_files": subjects,
            "before": {relative: ".saipen/evidence/T-1714-diagnostics/before/" + relative
                       for relative in subjects}, "timeout": 180}
output.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"contract": str(output), "context_entries": len(context),
                  "oracle_files": len(oracle), "subject_files": len(subjects),
                  "limits": "No root Git/memory, bytecode cache, live consumer, browser or installation context."}))
