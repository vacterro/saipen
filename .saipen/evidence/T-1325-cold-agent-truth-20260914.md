# T-1325 cold-agent truth evidence — 2026-09-14

Scope: bounded cold orientation, freshness provenance, bounded live indexes,
witness-scope reconciliation, and recovery-preservation regressions. Project
history remains data; no system-prompt injection, mtime authority, repository-
wide search, or historical LOG/BOARD rewrite was used.

## Implemented contract

- `saipen context orient --json` is the bounded cold-boot projection. It reports
  project identity/lineage, phase, task, last event, next action, blocker/wait,
  runtime generation, handoff status, and cheap implementation freshness.
- Handoffs carry provenance (`based_on_event`, identity, lineage, generation).
  CURRENT/STALE/FOREIGN/CONFLICT is machine-detected; current STATE/BOARD/LOG
  truth always wins and handoffs remain historical input.
- New LOG events are capped at 1024 bytes and new/updated BOARD records at 1200
  characters. Oversize writes externalize detail or return actionable refusal;
  old records remain untouched.
- Evidence uses the closed UNIT/INTEGRATION/EFFECT_PATH/LIVE/MANUAL taxonomy.
  A witness below a criterion's minimum reconciles as
  `EVIDENCE_SCOPE_TOO_WEAK`; escaped defects preserve prior PASS temporally.

## Verification

- `tools/test_cold_agent_truth.py`: 17 passed (including zero-context subprocess
  orientation, stale/foreign handoffs, mtime independence, read budget,
  bounded LOG/BOARD, effect-path scope, and escaped-defect truth).
- `tools/test_acceptance.py`: 25 passed; `tools/test_metrics_acceptance.py`: 26
  passed; T-1324 recovery reachability: 62 passed; immutable-ledger recovery:
  4 passed.
- Ruff and `git diff --check` pass for changed implementation/tests.
- T-1324 live acceptance against exact AUDAPACK, SAITULS, and FastPrompter roots
  remains recorded in `T-1324-live-acceptance-20260914.md`.

## Boundary classification

The final core boundary is recorded with `PATCH_OWNED=0` and `UNKNOWN=0`.
Known unrelated failures remain classified `PRE_EXISTING` only; they are not
attributed to T-1325.
