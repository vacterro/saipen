"""Read-only lifting evidence: preserve actual guard and unchanged route caps."""
import ast
import hashlib
import json
import sys
from pathlib import Path

root = Path.cwd()
evidence = root / ".saipen/evidence/T-1842-context-budget"
proposal = evidence / "proposal"
ship = proposal / "saipen/phases/ship.md"
saved = evidence / "failed-attempt/ship.md"
if ship.read_bytes() != saved.read_bytes():
    raise RuntimeError("Proposal must start from the exact preserved attempt")
text = ship.read_text(encoding="utf-8")
changes = [
    ("CORE \u00a71.3: no commit/tag/push; check Git separately. Run Board/README/version/\n"
     "junk/local metadata/core; omit tag equality; skip remote classification/staging/\nship gate.",
     "CORE \u00a71.3: no commit/tag/push. It does NOT mean git is absent; check Git.\n"
     "Run Board/README/version/junk/local metadata/core; omit tag equality; skip\n"
     "remote classification/staging/ship gate."),
    ("6b. GIT (repository/remote writes), ordered:",
     "6b. **GIT.** Repository/remote writes, ordered:"),
    ("## Closure mode BEFORE Git scope", "## Closure BEFORE Git scope"),
    ("- cohort: shared verified batch (e.g. main.py), no fictional per-ticket blobs:",
     "- cohort: shared verified batch, no fictional per-ticket blobs:"),
    ("## Procedure", "## Steps"),
    ("Mandatory\nverification/REVIEW green.", "Required\nverification/REVIEW green."),
    ("enters DONE. Work was DOING at entry; REVIEW never closes it.",
     "enters DONE. REVIEW never closes it."),
]
for before, after in changes:
    if text.count(before) != 1:
        raise RuntimeError("Proposal precondition mismatch: " + before[:60])
    text = text.replace(before, after, 1)
ship.write_text(text, encoding="utf-8", newline="\n")

# Run the actual repository validator branch. No copied/reimplemented condition.
validator = root / "tools/validate.py"
tree = ast.parse(validator.read_text(encoding="utf-8-sig"))
nodes = []
for node in ast.walk(tree):
    if isinstance(node, ast.If) and any(
        isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "fail"
        and stmt.value.args and isinstance(stmt.value.args[0], ast.Constant)
        and isinstance(stmt.value.args[0].value, str)
        and stmt.value.args[0].value.startswith("cross-doc drift [no-publish-split]")
        for stmt in node.body
    ):
        nodes.append(node)
if len(nodes) != 1:
    raise RuntimeError("Validator guard not uniquely identified")
code = compile(ast.Module(body=nodes, type_ignores=[]), str(validator), "exec")
outcomes = {}
for name, path in (("known_good", evidence / "prefix/ship.md"),
                   ("known_bad", saved), ("proposal", ship)):
    errors = []
    exec(code, {"_ship_t": path.read_text(encoding="utf-8"), "fail": errors.append})
    outcomes[name] = errors
sys.path.insert(0, str(root / "tools"))
import protocol_budget

budget_errors = protocol_budget.check(proposal / "saipen")
before_meta = json.loads((evidence / "before.json").read_text(encoding="utf-8"))
paths = ["saipen/COMMANDS.md", "saipen/phases/verify.md", "saipen/phases/ship.md"]
report = {
    "scope": "Diagnostic proposal: actual validator branch and budget checker; not full conformance/publication",
    "validator_sha256": hashlib.sha256(validator.read_bytes()).hexdigest(),
    "guard_outcomes": outcomes, "budget_errors": budget_errors,
    "proposal_ship_bytes": len(ship.read_bytes()),
    "subject_sha256": {rel: hashlib.sha256((proposal / rel).read_bytes()).hexdigest() for rel in paths},
    "live_source_unchanged": all((root / rel).read_bytes() ==
                                 (root / before_meta[rel]["backup"]).read_bytes() for rel in paths),
    "semantic_delta": "Restore original no-publish permission and GIT boundary markers; retain all constraints. "
                      "The illustrative main.py overlap remains in saved source/semantic trace. "
                      "DOING-at-entry remains enforced by procedure step 0; remove only its repeated exit wording.",
}
(evidence / "proposal-proof.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
if outcomes["known_good"] or not outcomes["known_bad"] or outcomes["proposal"] or budget_errors:
    raise RuntimeError("Proposal not proven; do not apply")
