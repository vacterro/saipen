"""Exercise the actual complete SHIP cross-doc block before another live edit."""
import ast
import json
import shutil
import sys
from pathlib import Path

root = Path.cwd()
evidence = root / ".saipen/evidence/T-1842-context-budget"
proposal = evidence / "proposal-all-guards"
shutil.copytree(root / "saipen", proposal / "saipen")
path = proposal / "saipen/phases/ship.md"
text = path.read_text(encoding="utf-8")
changes = [
    ("4. Before ANY external write: read origin, git ls-remote --heads --tags origin.",
     "4. **Classify the remote BEFORE any external write.** Read origin;\n"
     "   git ls-remote --heads --tags origin."),
    ("   4. Explicit reviewed owned paths ONLY; git add . / git add -A forbidden.",
     "   4. Stage ONLY the reviewed files this ship owns; explicit paths.\n"
     "      **`git add .` and `git add -A` are\n      forbidden here**."),
    ("   6. tools/validate.py --gate ship NOW: nonempty index/discovered release\n"
     "      paths; reject staged/working version divergence.",
     "   6. Run `tools/validate.py --gate ship` NOW: nonempty index/discovered\n"
     "      release paths; reject staged/working version divergence."),
    ("   8. Commit exact staged scope; never -a/widening paths.",
     "   8. Commit exactly the staged scope; never -a/widening paths."),
    ("   9. Push branch. Recheck first-publish immediately before branch AND tag:",
     "   9. **Push the branch.** Recheck first-publish immediately before branch AND tag:"),
    ("7. ONLY after branch push LANDED (success or fetched remote branch = local),\n"
     "   create vVERSION; push only:",
     "7. ONLY AFTER step 6b's branch push has LANDED (success or fetched remote\n"
     "   branch = local), create vVERSION; push only:"),
    ("0. Ticket every shipped unit; active Work stays ## DOING (CORE \u00a71.2 freshness/\n"
     "   attribution). Terminal cohort/crew: DONE/task none, cohort registry authority.",
     "0. Ticket every shipped unit (CORE \u00a71.2 freshness/attribution).\n"
     "   The shipped ticket was still in `## DOING` when this phase began; stays so.\n"
     "   Terminal cohort/crew: DONE/task none, cohort registry authority."),
    ("(T-1302/FastPrompter). Choose first:\n", "Choose first:\n"),
    ("- inherited_verified: NO delta; independent proof, durable publication\n"
     "  authority elsewhere. BUILD no-delta, VERIFY PASS, REVIEW PASS; then:",
     "- inherited_verified: NO delta; independently verify durable publication\n"
     "  authority elsewhere. BUILD no-delta/VERIFY PASS/REVIEW PASS; then:"),
    ("2. Before push align canonical VERSION, root/all discovered locale README badges\n"
     "   (exactly once), newest CHANGELOG and vVERSION tag.\n"
     "   Binding ship validator discovers kitchen mirrors; no second list.",
     "2. Align canonical VERSION, root/discovered locale README badges (exactly once),\n"
     "   newest CHANGELOG and vVERSION before push. Binding ship validator\n"
     "   discovers kitchen mirrors; no duplicate list."),
    ("5. After last metadata edit: tools/validate.py --gate core. Producer freshness\n"
     "   gates consumption, not Core ship. Core signals; staged-set gate binds.",
     "5. After last metadata edit: tools/validate.py --gate core. Producer freshness\n"
     "   gates consumption, not Core ship; Core signals, staged-set gate binds."),
    ("Success/intentionally skipped publish: overwrite .saipen/kitchen/digest.md\n"
     "with three short lines done:, remaining:, awaiting:. Snapshot, not history.",
     "Success/intentionally skipped publish: overwrite .saipen/kitchen/digest.md\n"
     "with three short lines done:, remaining:, awaiting: (snapshot, not history)."),
]
for before, after in changes:
    if text.count(before) != 1:
        raise RuntimeError("Proposal input changed: " + before[:60])
    text = text.replace(before, after, 1)
path.write_text(text, encoding="utf-8", newline="\n")

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
if len(ship_nodes) != 1 or len(split_nodes) != 1:
    raise RuntimeError("Actual validator blocks not uniquely identified")
code = compile(ast.Module(body=ship_nodes + split_nodes, type_ignores=[]), str(validator), "exec")
outcomes = {}
for label, source in (("original_good", evidence / "prefix/ship.md"),
                      ("saved_bad", evidence / "failed-attempt/ship.md"),
                      ("current", root / "saipen/phases/ship.md"), ("proposal", path)):
    warnings, failures = [], []
    namespace = {"rfc_path": root / "saipen/CORE.md", "_ship_doc": source,
                 "drift_ok": True, "warn": lambda category, msg: warnings.append(msg),
                 "fail": failures.append}
    exec(code, namespace)
    outcomes[label] = {"warnings": warnings, "failures": failures}
sys.path.insert(0, str(root / "tools"))
import protocol_budget

errors = protocol_budget.check(proposal / "saipen")
report = {"scope": "Actual complete SHIP cross-doc block + no-publish guard; diagnostic only",
          "outcomes": outcomes, "budget_errors": errors, "ship_bytes": len(path.read_bytes())}
(evidence / "all-ship-guards-proof.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"guard_counts": {k: {name: len(items) for name, items in v.items()}
                                   for k, v in outcomes.items()}, "budget_errors": errors,
                  "ship_bytes": report["ship_bytes"]}, indent=2))
if outcomes["original_good"]["warnings"] or outcomes["original_good"]["failures"]:
    raise RuntimeError("Original positive control unavailable")
if not (outcomes["saved_bad"]["warnings"] or outcomes["saved_bad"]["failures"]):
    raise RuntimeError("Known-bad negative control unavailable")
if outcomes["proposal"]["warnings"] or outcomes["proposal"]["failures"] or errors:
    raise RuntimeError("Proposal remains incomplete; do not apply")
