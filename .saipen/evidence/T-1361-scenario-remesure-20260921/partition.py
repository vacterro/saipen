"""Materialize the reviewed causal partition without altering the raw capture."""
import collections
import json
from pathlib import Path
import re

HERE = Path(__file__).parent
lines = (HERE / "run-console.txt").read_text(encoding="utf-16").splitlines()
records = [(n + 1, line[8:]) for n, line in enumerate(lines) if line.startswith("FAILED:")]
summary = records.pop(0)
assert len(records) == 87
rows = []
for ordinal, (line_number, raw) in enumerate(records, 1):
    identity = raw.split(":", 1)[0]
    root = "pending"
    classification = "UNKNOWN"
    cause = "Focused subprocess evidence pending; do not infer cause from truncated output."
    invariant = "Scenario-specific assertion"
    exit_code = "not retained by baseline assertion"
    downstream = []
    if ordinal <= 16:
        root, classification = "HOME-ROOT-FILE-SET", "DIRTY_SOURCE_DEPENDENT"
        cause = "Validator inspected HOME root handoff files; preserved relocation removed this first failure. Current 38-fixture run is green."
        invariant, exit_code = "Closed repository root file set", 1
    elif ordinal in (17, 18, 19):
        root = {17: "INJECT-SHELL-BYTES", 18: "INJECT-POWERSHELL", 19: "UNINSTALL-JSON-READER"}[ordinal]
        invariant = {17: "User bytes outside managed block remain identical", 18: "Managed BOOT+STYLE Aider block installed", 19: "Scheduler cleanup succeeds without schtasks"}[ordinal]
        classification = "FIXTURE_STALE" if ordinal == 19 else "ENGINE_DEFECT"
        cause = {17: "inject.sh template no longer starts with separator LF; uninstaller still removes one preceding byte, consuming user-owned newline (b2343541 template migration).",
                 18: "inject.ps1:593 calls Buffer.BlockCopy with four arguments; required count argument is absent. Focused subprocess retains exact PowerShell exception.",
                 19: "Fixture PATH=/usr/bin:/bin removes Python as well as schtasks on Windows. Registry-driven hook cleanup requires a JSON reader (b2343541); runtime source cleanup itself succeeds. Supply Python independently while preserving absent schtasks."}[ordinal]
        exit_code = 0 if ordinal == 17 else 1
    elif 20 <= ordinal <= 29:
        root, classification = "HOME-ROOT-FILE-SET", "DIRTY_SOURCE_DEPENDENT"
        cause = "Historical ambient HOME failure; exact existing project-root and last-event families now pass (7 each); output contract unchanged."
        invariant, exit_code = "Validator must accept valid fixture while retaining root/marker negative controls", 1
    elif 30 <= ordinal <= 33:
        root, classification = "FRESHNESS-COPIED-BOARD", "FIXTURE_STALE"
        cause = "Copied BOARD pruning removes needs edges but not blocked_on/resume reservations; baseline names dangling T-1361 and partial T-1426. Root handoffs also copied. Empty-index assertion has an independent diagnostic mismatch requiring focused inspection."
        invariant, exit_code = "Fixture BOARD must retain coherent dependency reservations before testing staged metadata", 1
    elif raw.startswith("release executor"):
        family = re.search(r"release executor (\d+[a-z]?)", raw).group(1)
        is_root = family in {"3h", "4a", "4j", "8a"} or (family in {"11c", "14", "15"} and "succeeds:" in raw or family == "14" and "returns RELEASED:" in raw)
        root = "RELEASE-COPIED-ROOT" if family in {"11c", "14"} else "RELEASE-SCOPE-ORDER"
        classification = "FIXTURE_STALE" if is_root else "DOWNSTREAM_SYMPTOM"
        cause = ("Copied untracked HOME root handoffs fail the fixture validator." if root == "RELEASE-COPIED-ROOT" else
                 "build_fixture records scope before changing VERSION, CHANGELOG and locale bytes; tree binding correctly refuses STALE_PLAN (contract commit 6e47c37c).")
        invariant = "Reviewed scope tree must equal the intended final source tree before release"
        exit_code = 1 if "rc=1" in raw else "RELEASE_FAILED / subprocess code not retained"
        if family.startswith("9"):
            cause += " Injection edge was not reached; recovery conclusions remain unproven until first release operation succeeds."
        if classification == "DOWNSTREAM_SYMPTOM":
            downstream = ["No successful release predecessor; absence of commit/tag/scope/clone content is not independently diagnosed."]
    elif 76 <= ordinal <= 82 or ordinal in (84, 85, 87):
        root, classification = "HOME-ROOT-FILE-SET", "DIRTY_SOURCE_DEPENDENT"
        cause = "Historical HOME root handoffs contaminated validator; style/memory prose is WARN diagnostic tail, not engine result pollution. Improve 192 and nitro-integrity 191 checks now green, including exact composite refs and closure controls; H30 now green in continuity subprocess. Recovery A/B remain to remeasure in full suite."
        invariant, exit_code = "Valid synthetic project accepted by canonical validator", 1
    elif ordinal == 83:
        root, classification = "BOARD-EMPTY-SECTION", "FIXTURE_STALE"
        cause = "Fixture inserts physical '- none' records in canonical sections; closed BOARD grammar intentionally rejects them (b2343541). Current focused RED reproduced."
        invariant = "Canonical empty sections contain no physical records"
        exit_code = "in-process validate_project returns BOARD errors"
    elif ordinal == 86:
        root, classification = "ATTEMPT-RECOVERY-VALIDATION-ORDER", "DOWNSTREAM_SYMPTOM"
        cause = "H26b is FOREIGN actor replay, not same-actor idempotence. H26a predecessor close fails validation before stale claim release is included. Failed adoption leaves a1's original attempt active, so its replay truthfully returns ATTEMPT_ACTIVE. Current full subprocess additionally exposes H12 future-version fixture stale and same recovery cascade SC C2/H18c/H18d."
        invariant, exit_code = "Validate recovery's complete final BOARD and STATE together", 1
    rows.append({"id": f"B{ordinal:03d}", "capture_line": line_number, "identity": identity,
                 "raw_failure": raw, "root": root, "first_causal_failure": cause,
                 "exit_code": exit_code, "first_failing_invariant": invariant,
                 "downstream_symptoms": downstream, "likely_owner": "T-1361",
                 "classification": classification})
(HERE / "failure-identities.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(collections.Counter(row["classification"] for row in rows))
