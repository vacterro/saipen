"""Preserve every actual SHIP/borrowed-invariant anchor, with original caps."""
import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path

root = Path.cwd()
evidence = root / ".saipen/evidence/T-1842-context-budget"
proposal = evidence / "proposal-all-guards/saipen"
ship = proposal / "phases/ship.md"
text = ship.read_text(encoding="utf-8")
start = text.index("Publish reviewed Work:")
end = text.index("PUBLISH is action, not phase.", start)
# Remove only the repeated procedure summary: all ordered effects remain in
# numbered steps and atomic exit, with their exact protected validator anchors.
text = text[:start] + "Publish reviewed Work. " + text[end:]
assert text.count("recreate local tag") == 1
assert text.count("Step 7 kept tag unpushed; ") == 1
text = text.replace("recreate local tag", "recreate unpushed local tag")
text = text.replace("Step 7 kept tag unpushed; ", "")
ship.write_text(text, encoding="utf-8", newline="\n")

verify = proposal / "phases/verify.md"
text = verify.read_text(encoding="utf-8")
changes = [
    ("-> smoke. First mandatory failure stops PASS; later green cannot override it.\n",
     "-> smoke. First failed mandatory gate: this pass cannot claim PASS;\nlater green cannot override it.\n"),
    ("Read KNOWLEDGE/ canonical commands (SCOUT records once); absent: derive from\nbuild/CI.",
     "Read the project's canonical commands from `KNOWLEDGE/` (SCOUT records once);\nabsent: derive from build/CI."),
    ("Before broad negatives run known-good control. Failure means unavailable/\n"
     "failed instrument: repair verifier, do not fail subject. Distinguish mandatory\n"
     "subject failure. Pin verifier versions/explicit rules; defaults may change\n"
     "verdicts for identical bytes.",
     "Known-good control before broad negatives. Failure means verifier unavailability,\n"
     "not subject failure: repair it. Pin verifier versions/explicit rules;\n"
     "unpinned defaults can change verdicts for identical bytes."),
]
for before, after in changes:
    if text.count(before) != 1:
        raise RuntimeError("VERIFY proposal input changed: " + before[:50])
    text = text.replace(before, after, 1)
verify.write_text(text, encoding="utf-8", newline="\n")

# Positive and negative controls preserve the complete original protocol inputs.
good = evidence / "original-protocol/saipen"
shutil.copytree(root / "saipen", good)
bad = evidence / "failed-protocol/saipen"
shutil.copytree(root / "saipen", bad)
for rel, name in (("COMMANDS.md", "COMMANDS.md"),
                  ("phases/verify.md", "verify.md"), ("phases/ship.md", "ship.md")):
    (good / rel).write_bytes((evidence / "prefix" / name).read_bytes())
    (bad / rel).write_bytes((evidence / "failed-attempt" / name).read_bytes())

validator = root / "tools/validate.py"
tree = ast.parse(validator.read_text(encoding="utf-8-sig"))
ship_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.If)
              and ast.unparse(node.test) == "_ship_doc.is_file()"]
split_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.If) and any(
    isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
    and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "fail"
    and stmt.value.args and isinstance(stmt.value.args[0], ast.Constant)
    and isinstance(stmt.value.args[0].value, str)
    and stmt.value.args[0].value.startswith("cross-doc drift [no-publish-split]")
    for stmt in node.body)]
markers = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
           and any(isinstance(target, ast.Name) and target.id == "_markers" for target in node.targets)
           and "cheapest-first" in ast.unparse(node)]
marker_loops = [node for node in ast.walk(tree) if isinstance(node, ast.For)
                and isinstance(node.iter, ast.Name) and node.iter.id == "_markers"
                and "borrowed-invariants" in ast.unparse(node)]
if any(len(group) != 1 for group in (ship_nodes, split_nodes, markers, marker_loops)):
    raise RuntimeError("Actual validator source blocks are not unique")
code = compile(ast.Module(body=ship_nodes + split_nodes + markers + marker_loops,
                          type_ignores=[]), str(validator), "exec")
outcomes = {}
for name, directory in (("original_good", good), ("saved_bad", bad),
                        ("current", root / "saipen"), ("proposal", proposal)):
    warnings, failures = [], []
    exec(code, {"rfc_path": directory / "CORE.md", "_ship_doc": directory / "phases/ship.md",
                "drift_ok": True, "warn": lambda category, msg: warnings.append(msg),
                "fail": failures.append})
    outcomes[name] = {"warnings": warnings, "failures": failures}
sys.path.insert(0, str(root / "tools"))
import protocol_budget

errors = protocol_budget.check(proposal)
paths = ("COMMANDS.md", "phases/verify.md", "phases/ship.md")
report = {"scope": "Actual complete SHIP/no-publish/borrowed-invariant code and route-budget diagnostic; not full conformance",
          "outcomes": outcomes, "budget_errors": errors,
          "files": {rel: {"sha256": hashlib.sha256((proposal / rel).read_bytes()).hexdigest(),
                          "lf_bytes": len((proposal / rel).read_bytes().replace(b"\r\n", b"\n"))}
                    for rel in paths},
          "validator_sha256": hashlib.sha256(validator.read_bytes()).hexdigest()}
(evidence / "complete-proposal-proof.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"guard_counts": {key: {kind: len(items) for kind, items in value.items()}
                                   for key, value in outcomes.items()},
                  "budget_errors": errors, "files": report["files"]}, indent=2))
if outcomes["original_good"]["warnings"] or outcomes["original_good"]["failures"]:
    raise RuntimeError("Original positive control unavailable")
if not outcomes["saved_bad"]["failures"]:
    raise RuntimeError("Known-bad control unavailable")
if outcomes["proposal"]["warnings"] or outcomes["proposal"]["failures"] or errors:
    raise RuntimeError("Proposal remains incomplete; do not apply")
