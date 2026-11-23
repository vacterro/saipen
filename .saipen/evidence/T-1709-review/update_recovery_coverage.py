"""Record bounded recovery facts without upgrading the negative current preflight."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE = ".saipen/evidence/T-1709-review/REVIEW.md;.saipen/evidence/T-1709-review/recovery-readback.json;.saipen/evidence/AUDAPACK-recovery-20261010/phase4-v3.json"
UPDATES = [
    ("SRC-210", "R006", "VERIFIED", "Prior isolated controls A-G all passed before the actual canonical recovery, recorded in phase1-v5.json and phase4-v3.json. Current readback proves preserved mapped copies and valid new-root ledger; no new recovery transaction or fake current original-baseline PASS."),
    ("SRC-210", "R007", "VERIFIED", "The required scoped approval exists in later SRC-211 and was already executed through canonical INIT (phase3.json, E-14276). No second approval, recreated epoch or rewritten original is invented. Current complete original-baseline discrepancy is retained separately in SRC-211 R002."),
    ("SRC-210", "R008", "VERIFIED", "Independent current readback: recovery lineage-0ee6b060c73040d2be567d123691d079 remains AUTHORIZED with native PASS, complete error-free ledger/receipts and no pending/conflicts. Original lineage remains UNAUTHORIZED/NO_GO. Saved mappings 28517/28517 match; neither external root changed during reads. No live host enforcement, consumer enablement, cutover or full original-baseline PASS claimed."),
    ("SRC-210", "R009", "VERIFIED", "Existing T-1709 resumed after E-14276 recovery acceptance and DONE prerequisites T-1705/T-1703/T-1707. Current correction oracle 14/14 and transport neighbors 96 (2 skips) pass. One actual oldest audit intake created SRC-212/T-1711 while preserving T-1709 ownership."),
    ("SRC-210", "R010", "VERIFIED", "Historical apply-append's unwanted T-1710 remains visibly BLOCKED AMENDMENT_ONLY with its Source/event. It was not executed or called DONE; this run created no independent generic amendment Work and did not erase the historical violation. Steering continues in existing T-1709/T-1702; T-1711 owns a distinct real audit."),
    ("SRC-211", "R001", "VERIFIED", "Historical phase0..phase4-v3 prove the scoped independent INIT and preserved original. This run performed only fresh readback at the two existing roots; inventories prove zero external-root byte mutations, no INIT, cutover, publication or historical event invention."),
    ("SRC-211", "R002", "BLOCKED", "Renewed original-baseline preflight is not admitted: four audit/archive files added and two audit helpers missing versus phase0; no retained original file changed content. Original has 4764 hardlinks, sampled into .tmp.driveupload. Original/ref identity and all saved recovery mappings match. Cause of audit removals remains unknown; no new original-root operation is authorized from this result."),
    ("SRC-211", "R003", "VERIFIED", "Actual prior phase1-v5.json has all seven A-G controls PASS, including canonical INIT positive, existing namespace, corrupt ledger and unsupported DONE refusals, foreign/stale bindings, partial-init nonacceptance and unauthorized zero-byte refusal. Preserve these executed controls rather than invent a rerun."),
    ("SRC-211", "R004", "VERIFIED", "Inspected existing _init_command: optional provisioning only when no mailbox bound and executable available. Actual prior acceptance proves external_mailbox_unmodified; this readback performed no INIT or provisioning."),
    ("SRC-211", "R005", "VERIFIED", "Current recovery inventory verifies all 28517 passive original/supporting mappings by exact digest/size, distinct source/destination nodes and destination nlink 1. Recovery has zero alias risks; Git refs/history match baseline. Original's later inbox changes and driveupload links are disclosed under R002, not erased or mislabeled as original-baseline preservation."),
    ("SRC-211", "R006", "VERIFIED", "Prior phase3.json records the actual installed canonical CLI INIT, current actual new lineage differs from original; phase4-v3 validates generated authority and real checkpoint operation. No manual lifecycle file creation, second INIT or synthetic historical Work in this run."),
    ("SRC-211", "R007", "VERIFIED", "Current new-root native core PASS; complete ledger and semantic receipt validation have zero errors, pending or conflicts. Its original authorized E-1 checkpoint remains operation-backed. Prior real foreign-lineage and protected-write controls refused with zero-byte changes; 28517 destination mappings and original/ref checks repeated read-only. Root-wide original baseline remains explicitly negative."),
    ("SRC-211", "R008", "VERIFIED", "Original is NO_GO/UNAUTHORIZED; existing recovery root is AUTHORIZED for canonical operations only. Current full original-baseline readback failed, and no renewed recovery, consumer activation, cutover, publication or historical DONE import was performed. These are separate verdicts, not one universal PASS."),
    ("SRC-211", "R009", "VERIFIED", "Existing fairness Work T-1709 owns the seat at VERIFY; prerequisites T-1705/T-1703/T-1707 are actually DONE. Native core 0 problems/9 warnings after executed T-1695 RV-000019; no ownership or priority override. Actual oldest-source intake queued T-1711."),
    ("SRC-211", "R010", "IMPLEMENTED", "Exact-generation chronology and nonurgent fairness exercised by 14-case oracle and 96 neighbors; source SRC-212/Work T-1711 are actual exact intake for oldest audit. No current cleanup: 7 pending (1 captured,6 NEW), zero files consumed this run; no unclosed generation deleted. Complete-family evidence still pending and T-1711 continuation remains queued."),
    ("SRC-211", "R011", "VERIFIED", "T-1710 stays parked AMENDMENT_ONLY with preserved Source authority; existing SRC-209 implementation reused and corrected under T-1709. SRC-210 remains ACTIVE; no silent closure or duplicate generic recovery Work."),
    ("SRC-211", "R012", "DEFERRED", "Current facts and explicit limits are in REVIEW.md and immutable readback evidence. Full family still running; actual T-1711 continuation and original-baseline discrepancy remain open. No global cc all completion or universal recovery PASS is claimed."),
]
output = HERE / "recovery-coverage-operations.json"
if output.exists():
    raise SystemExit("Existing coverage evidence is immutable")
records = []
for receipt, rid, disposition, verification in UPDATES:
    command = [str(ROOT / "bin/saipen.cmd"), "source", "disp", receipt, rid,
               disposition, "--evidence", EVIDENCE, "--verification", verification, "--json"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=120)
    records.append({"receipt": receipt, "rid": rid, "exit_code": run.returncode,
                    "stdout": run.stdout, "stderr": run.stderr})
    output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    if run.returncode or not json.loads(run.stdout).get("ok"):
        raise SystemExit(run.stdout + run.stderr)
print(json.dumps({"updated": len(records), "open_original_preflight": "SRC-211:R002",
                  "full_family_pending": True, "evidence": str(output)}))
