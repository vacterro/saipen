"""Exercise ledger and existing journal predicates on disposable copied bytes."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
BASE = HERE / "captured-project"
TARGET = Path("V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_ZAICODE")
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import journal, log

operation = "finish-4e77c05c4d31478ebbb7e73e6df1d1ed"
record = journal.Journal(TARGET, operation).read()
expected = record["read_preconditions"][".saipen/logs"]
assert record["status"] == "COMMITTED"
assert journal.hash_tree_dependency(BASE / ".saipen/logs") == expected
assert journal._recovery_identity_binding(BASE, record)["ok"]
assert not log.history_contract_errors(BASE)
base_files = {p.relative_to(BASE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in BASE.rglob("*") if p.is_file()}
results = []
for name in ("missing-parent", "duplicate-event", "reordered-events", "forged-parent",
             "modified-sealed", "cross-project-ledger", "incorrect-lineage",
             "stale-history-snapshot", "incomplete-restoration"):
    with tempfile.TemporaryDirectory(prefix="negative-", dir=HERE) as directory:
        root = Path(directory).resolve()
        assert root.is_relative_to(HERE.resolve()), "cleanup target escaped evidence workspace"
        shutil.copytree(BASE / ".saipen/logs", root / ".saipen/logs")
        for filename in ("LOG.md", "IDENTITY.md"):
            shutil.copyfile(BASE / ".saipen" / filename, root / ".saipen" / filename)
        path = root / ".saipen/logs/LOG-004.md"
        raw = path.read_bytes()
        lines = raw.splitlines(keepends=True)
        at = next(i for i, line in enumerate(lines) if b"[E-3133]" in line)
        if name == "missing-parent":
            del lines[at]
        elif name == "duplicate-event":
            lines.insert(at + 1, lines[at])
        elif name == "reordered-events":
            lines[at], lines[at + 1] = lines[at + 1], lines[at]
        elif name == "forged-parent":
            lines[at + 1] = lines[at + 1].replace(b"parent: E-3133", b"parent: E-9999999")
        elif name == "modified-sealed":
            lines[at] = lines[at].rstrip(b"\r\n") + b" CONTROL_MODIFIED\n"
        elif name == "cross-project-ledger":
            lines = [(Path("V:/___VAC/__K/__CODE/__SAITULS") / ".saipen/LOG.md").read_bytes()]
        elif name == "incorrect-lineage":
            identity = root / ".saipen/IDENTITY.md"
            text = identity.read_text(encoding="utf-8")
            text = re.sub(r"lineage-[0-9a-f]{32}", "lineage-" + "1" * 32, text)
            identity.write_text(text, encoding="utf-8")
        elif name == "stale-history-snapshot":
            captured = log.read_history_snapshot(root)
            lines.append(b"\n")
        elif name == "incomplete-restoration":
            # Only this disposable tree loses a segment. The captured source is immutable.
            (root / ".saipen/logs/LOG-002.md").unlink()
        path.write_bytes(b"".join(lines))
        errors = log.history_contract_errors(root)
        identity = journal._recovery_identity_binding(root, record)
        current = journal.hash_tree_dependency(root / ".saipen/logs")
        changed = current != expected
        rejected = bool(errors or not identity["ok"] or changed)
        if name in {"missing-parent", "duplicate-event", "reordered-events", "forged-parent"}:
            assert errors, f"structural ledger predicate missed {name}"
        if name == "incorrect-lineage":
            assert not identity["ok"] and identity["code"] == "PROJECT_MISMATCH"
        if name == "stale-history-snapshot":
            assert captured.hash != log.read_history_snapshot(root).hash
        assert rejected, name
        results.append({"case": name, "rejected": rejected, "ledger_errors": errors,
                        "identity_verdict": identity, "sealed_dependency_changed": changed,
                        "level": "existing predicate; not an authorized restoration/effect-path proof"})
after = {p.relative_to(BASE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in BASE.rglob("*") if p.is_file()}
assert after == base_files
result = {"positive_control": "valid copy, original committed finish lineage and sealed digest match",
          "original_operation": operation, "expected_sealed_dependency": expected,
          "cases": results, "captured_inputs_preserved": True,
          "limitation": "No recovery transaction was approved or executed; structural syntax alone cannot authenticate a legal text rewrite."}
(HERE / "negative-controls.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"cases": len(results), "rejected": sum(r["rejected"] for r in results),
                  "captured_inputs_preserved": True, "scope": "predicate controls"}))
