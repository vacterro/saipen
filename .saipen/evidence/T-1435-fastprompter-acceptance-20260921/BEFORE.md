# T-1435 M11 -- real FastPrompter BEFORE ship gate (2026-09-21)

Project: V:/___VAC/__K/__CODE/_PY/_FastPrompter (verified binding; lineage
lineage-c13f771bc2924a5a81b65fc79e5aca08 per its own IDENTITY carrier).
Command: `python tools/validate.py --gate ship` run from the project root
(the project shim delegates to the canonical validator of the selected home).

## A. Live installed runtime (no SAIPEN_HOME override -> C:/Users/vac34/.agents/skills/saipen, VERSION 8.0.1)

exit 1; Validation FAILED: 51 problem(s), 66 warning(s); file fp-before-old.txt
Historical four blocker classes confirmed present:
  1. source receipts -- BOARD Work T-1226 references missing source receipt
     FASTPROMPTER - SMART_20260908_0645
  2. saitranslate STATE.md lifecycle incoherent: DONE with non-empty task
  3. saiwiki STATE.md lifecycle incoherent: DONE with non-empty task
  4. saiwiki BOARD.md phase DONE while its board still holds open work

## B. Current reviewed runtime (SAIPEN_HOME=V:/_TEMP_/opencode/saipen-flat-t1435,
flattened copy of this worktree; lineage lineage-baeb688e509941f5903f854b37b6c05b)

exit 1; Validation FAILED: 52 problem(s), 66 warning(s); file fp-before-new.txt
Same four classes, each with the exact identity, plus:
  5. runtime namespace -- machine-local runtime artifacts are tracked by Git
     (.saipen/cache/continuation-liveness.json, .saipen/locks/continuation-liveness.lock,
     .saipen/locks/core.lock, .saipen/recovery/ops/checkpoint-*/staged, ...);
     classification OPERATOR_AUTHORIZED_COMMAND with the exact `git rm -r --cached`
     maintenance command in the finding.
The T-1226 finding now carries its executable canonical remediation:
  saipen ticket repair-metadata T-1226 --field source_receipts --legacy-unbound
  --authority lineage-baeb688e509941f5903f854b37b6c05b

No product runtime files were modified by this measurement. No manual BOARD/STATE/LOG
edit was performed.
