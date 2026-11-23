"""Export only campaign deltas against captured before-images, never HEAD ownership."""
import difflib
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
pairs={
 "tools/saipen_engine/registry.py":"tools__saipen_engine__registry.py",
 "tools/validate.py":"tools__validate.py",
 "tools/audit_checks.py":"audit_checks.before.py",
 "tools/validator_fail_sites.json":"tools__validator_fail_sites.json",
 "tools/test_protocol_registry.py":"tools__test_protocol_registry.py",
 "tools/test_vocabulary_parity.py":"tools__test_vocabulary_parity.py",
 "tools/test_remediation_self_consistency.py":"tools__test_remediation_self_consistency.py",
 "tools/test_t1647_machine_runtime.py":"tools__test_t1647_machine_runtime.py",
 "tools/test_t1654_project_block.py":"tools__test_t1654_project_block.py",
 "tools/test_t1839_cohort_reconciliation.py":"tools__test_t1839_cohort_reconciliation.py",
 "saipen/RUNTIME.md":"saipen__RUNTIME.md",
 "tools/saipen_engine/board.py":"tools__saipen_engine__board.py",
 "tools/saipen_engine/router.py":"tools__saipen_engine__router.py",
 "tools/saipen_engine/audit_inbox.py":"tools__saipen_engine__audit_inbox.py",
 "tools/saipen_engine/automation.py":"tools__saipen_engine__automation.py",
 "tools/saipen_engine/response_surface.py":"tools__saipen_engine__response_surface.py",
 "tools/saipen_engine/goal_authority.py":"tools__saipen_engine__goal_authority.py",
 "tools/saipen_engine/operations.py":"tools__saipen_engine__operations.py",
 "tools/saipen_engine/state.py":"tools__saipen_engine__state.py",
 "tools/saipen_engine/entry.py":"tools__saipen_engine__entry.py",
 "tools/saipen_engine/reconcile.py":"tools__saipen_engine__reconcile.py",
 "tools/saipen_engine/commands.py":"tools__saipen_engine__commands.py",
 "tools/saipen_engine/cold_truth.py":"tools__saipen_engine__cold_truth.py",
 "tools/saipen.py":"tools__saipen.py",
 "tools/test_cold_agent_truth.py":"tools__test_cold_agent_truth.py",
 "tools/saipen_engine/conformance.py":"tools__saipen_engine__conformance.py.lint",
 "tools/saipen_engine/finding_route.py":"tools__saipen_engine__finding_route.py.lint",
 "tools/saipen_engine/findings.py":"tools__saipen_engine__findings.py.lint",
 "tools/test_t1817_acceptance_bar.py":"tools__test_t1817_acceptance_bar.py.lint",
 "tools/test_t1817_diagnostic_ownership.py":"tools__test_t1817_diagnostic_ownership.py.lint",
 "tools/test_t1817_finding_route.py":"tools__test_t1817_finding_route.py.lint",
 "saipen/BOOT.md":"saipen__BOOT.md",
 "saipen/COMMANDS.md":"saipen__COMMANDS.md",
 "saipen/REGISTRY.json":"saipen__REGISTRY.json",
 "saipen/MANIFEST.json":"saipen__MANIFEST.json",
 "saipen/EXECUTION.md":"saipen__EXECUTION.W4.md",
 "tools/test_t1857_shared_blockers.py":None,
 "tools/test_t1857_budget_owner.py":None,
 "tools/test_t1858_valve_guidance.py":None,
 "saipen/COMMANDS_REFERENCE.md":None,
}
patch=[]
manifest=[]
for name,before in pairs.items():
    old=(OUT/"before"/before).read_text(encoding="utf-8-sig") if before else ""
    reconstructed=False
    if name=="saipen/EXECUTION.md":
        # Explicit reconstruction from the recorded W1 one-line wording patch.
        old=old.replace("STATUS: active phase/task or idle verdict.",
                        "STATUS: actual phase/task or justified WAIT.",1)
        reconstructed=True
    new=(ROOT/name).read_text(encoding="utf-8-sig")
    if old==new:
        continue
    old=old.replace("\r\n","\n")
    new=new.replace("\r\n","\n")
    patch.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),
                                    fromfile="a/"+name if before else "/dev/null",
                                    tofile="b/"+name))
    manifest.append({"path":name,"before_artifact":before,
                     "before_reconstructed_from_recorded_hunk":reconstructed,
                     "before_sha256":hashlib.sha256(old.encode()).hexdigest() if before else None,
                     "after_sha256":hashlib.sha256(new.encode()).hexdigest()})
(OUT/"OWNED-DELTA.patch").write_text("".join(patch),encoding="utf-8")
(OUT/"owned-files.json").write_text(json.dumps({
 "scope":"Incremental campaign delta against captured working bytes; not all file-vs-HEAD changes",
 "publication_authorized":False,"files":manifest,
 "caveat":"Requires the captured unpublished working baseline. This does not adopt foreign foundational content or staged entries."
},indent=2)+"\n",encoding="utf-8")
print(json.dumps({"owned_changed_files":len(manifest),"patch_bytes":len("".join(patch).encode())}))

