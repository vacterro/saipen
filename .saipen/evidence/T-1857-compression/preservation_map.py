"""Selected changed-rule preservation map; not full semantic or graph proof."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
registry = json.loads((ROOT / "saipen/REGISTRY.json").read_text())
manifest = json.loads((HERE / "owned-files.json").read_text())

def entry(identifier, rules, old, new, callers, contract, evidence, limitations=()):
    assert set(rules) <= registry["rule_owners"].keys()
    return {"change": identifier, "original_rule_ids": rules,
            "normative_owners_unchanged": {r: registry["rule_owners"][r] for r in rules},
            "old_implementation_or_projection": old, "new_implementation_or_projection": new,
            "affected_callers": callers, "preserved_contract": contract,
            "regression_evidence": evidence, "limitations": list(limitations)}

rows = [
    entry("goal budget fact and repeated threshold", ["GOAL-01"],
          ["operations and reconcile cap constants", "router/entry/CLI/state repeated predicates"],
          ["REGISTRY.goal_authority.limits", "goal_authority.budget_exhausted"],
          ["operations.py", "reconcile.py", "router.py", "entry.py", "state.py",
           "goal_authority.py", "tools/saipen.py"],
          "Same goal-only >= boundary at 3 waves OR 20 processed tickets; independent origin/grant checks and one-axis accounting remain distinct.",
          ["test_t1857_budget_owner.py:48-input equivalence matrix and import control",
           "test_t1858_valve_guidance.py:0/28 untrusted refusal, explicit kernel-origin recovery, 28/1000 queued records"],
          ["Native-origin test doubles do not prove the production host."]),
    entry("resume input/payload policy", ["CMD-CONTINUE-01", "CMD-ROUTING-01", "GOAL-01"],
          ["CLI allowlist and goal_authority hardcoded native input spellings"],
          ["REGISTRY.commands.resume", "commands.resume_policy"],
          ["tools/saipen.py:_continue", "goal_authority.fresh_cc_provenance"],
          "Declared resume forms and derived Cyrillic twins execute the existing pipeline. All does not create a goal or grant authority; invalid payloads and unsigned replays refuse.",
          ["frozen spelling/cc-all red and green logs", "test_t1858_valve_guidance.py",
           "final-contracts3.log"],
          ["Old red controls prove their captured oracle generation; later expanded suites are separately scoped."]),
    entry("shared blocker and idle classification", ["PICK-01", "SOURCE-AUDIT-INBOX-01"],
          ["board root/idle classification", "audit_inbox duplicated external/operator prioritization"],
          ["board.project_blockers", "board.classify_idle_work"],
          ["audit_inbox.py", "router.py", "automation.py", "tools/saipen.py:status"],
          "Retain ticket identities, all dependency roots and independent-work priority. Group four release roots/three dependents; 102 blocked plus TODO is not complete. Recorded blockers grant no recovery authority.",
          ["test_t1857_shared_blockers.py", "measurements.json:captured BOARD fixture",
           "blocker-projection.json"],
          ["This is conservative recorded metadata, not a live release authorization."]),
    entry("idle display and checker parity", ["EXEC-RESPONSE-01"],
          ["human status rendered lifecycle DONE", "checker required the literal lifecycle head"],
          ["response_surface._display_phase consumed by renderer and authoritative checker"],
          ["response_surface.gate_final_response", "tools/saipen.py:response check/render",
           "existing host Stop/check consumers"],
          "Machine lifecycle phase remains unchanged; only canonical automation supplies idle status. Blocked Work cannot claim DONE, active phases cannot be replaced, genuine operator WAIT remains admissible.",
          ["idle-delivery-red.log", "idle-delivery-green.log",
           "idle-gate-consumers-green.log", "prior-failure-rerun2.json"]),
    entry("missing-native-input guidance", ["GOAL-01", "INGRESS-AUTHORITY-01"],
          ["reset/executor/automation repeated generic run-cc directions"],
          ["goal_authority.bounded_resume_requirement"],
          ["goal_authority.reset_authority", "operations.py", "automation.py"],
          "Keep RECONCILE_REAUTH_REQUIRED/hard_wait and no agent recovery command. Describe genuine native input and the bridge owner; raw carrier fidelity is not operator identity.",
          ["test_t1858_valve_guidance.py", "P0-AUDAPACK-readback.json",
           "RUNTIME.md:authenticated continuation recovery"],
          ["No ZAICODE hook/issuer was installed; no real native positive exists."]),
    entry("conditional command inventory", ["CMD-ROUTING-01", "FUTURE-GATE-01"],
          ["COMMANDS.md API and alias tables; validator/audit/tests read that fixed path"],
          ["COMMANDS_REFERENCE.md derived inventory", "REGISTRY.commands.reference_document",
           "registry.command_reference_path"],
          ["tools/validate.py:publication/crew/shortcut checks and coverage",
           "tools/audit_checks.py:mutation target", "test_protocol_registry.py",
           "test_vocabulary_parity.py", "test_remediation_self_consistency.py",
           "test_t1647_machine_runtime.py", "test_t1654_project_block.py"],
          "COMMANDS retains semantics and Rule IDs; registry remains machine authority. Original forms remain discoverable through declared conditional inventory. Explicit missing/unsafe references refuse; legacy schema-1 location remains supported.",
          ["command-reference-owner-red.log", "doc-consumers-green.log",
           "reference-controls.json:executed missing/verb/shortcut 0/1/0 controls",
           "tools/validator_fail_sites.json:explicit covered identity changes",
           "final-contracts3.log"],
          ["First full integration failed and was repaired; its FAIL is preserved."]),
    entry("BOOT owner delegation", ["CMD-CONTINUE-01", "SOURCE-AUTHORITY-01",
                                      "RECOVERY-01", "CHECKPOINT-01", "CONTEXT-BUDGET-01"],
          ["BOOT repeated transport/binding/owner mechanics and complete command context"],
          ["BOOT consumes canonical route/work locators and delegates to existing owners"],
          ["cold-start agents", "existing boot/activation/entry/transport tests"],
          "Keep the closed entry table, START first, full STYLE/EXECUTION before output, exact source/contract, verified transport and fallback, current-input priority, checkpoint order and no forged provenance.",
          ["W4-OWNERSHIP.md:per-obligation map", "doc-consumers-green.log",
           "prior-failure-rerun2.json", "test_protocol_registry.py:one owner per registered Rule ID"],
          ["Unchanged unnumbered global law is not exhaustively classified by the marker inventory."]),
    entry("bounded STATE frontmatter projection", ["STATE-SHAPE-01", "CONTEXT-BUDGET-01"],
          ["cold_truth._read_state capped the entire historical Markdown file"],
          ["bounded complete-header read passed to the same strict state parser"],
          ["cold_truth orientation/read-only context"],
          "Do not delete state/history or raise limits. Require a complete terminated frontmatter fence; reject duplicate/malformed headers and short-read races; disclose omitted body.",
          ["test_cold_agent_truth.py:captured red/green and 21-test suite",
           "W6-W9-MEASUREMENTS.md:real FastPrompter orientation"],
          ["Read-only orientation does not grant mutation, admission or Source closure."]),
]

hashes = {}
for item in manifest["files"]:
    path = ROOT / item["path"]
    value = hashlib.sha256(path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode()).hexdigest()
    assert value == item["after_sha256"], f"Owned source changed: {item['path']}"
    hashes[item["path"]] = value

# Bounded static references enrich the map without pretending to have an MCP
# graph generation or complete dynamic call coverage.
targets = {"budget_exhausted", "resume_policy", "project_blockers",
           "classify_idle_work", "command_reference_path", "_display_phase",
           "bounded_resume_requirement"}
references = []
for relative in hashes:
    if not relative.endswith(".py"):
        continue
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8-sig"))
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for name in node.names:
                if name.name in targets:
                    imports[name.asname or name.name] = name.name
        if isinstance(node, ast.Call):
            symbol = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else "")
            target = imports.get(symbol, symbol)
            if target in targets:
                references.append({"path": relative, "line": node.lineno, "symbol": target})

result = {"scope": "All selected consolidations and removed explanations in the owned campaign delta",
          "source_sha256": hashes, "consolidations": rows,
          "bounded_ast_call_references": references,
          "limitations": ["MCP graph tools unavailable; no index generation/coverage claim.",
                          "AST evidence is bounded to owned Python files; dynamic and unrelated callers are not exhaustive.",
                          "This map is not a native LIVE, independent review, full PASS or campaign completion verdict."]}
(HERE / "semantic-preservation-map.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
print(json.dumps({"consolidations": len(rows), "owned_paths": len(hashes),
                  "bounded_static_references": len(references), "source_drift": []}))
