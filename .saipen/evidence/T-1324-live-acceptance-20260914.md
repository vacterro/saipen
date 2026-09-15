# T-1324 real-project recovery reachability acceptance — 2026-09-14

Scope: bounded read-only Fleet preflight and canonical recovery behavior against
the three exact operator-supplied project roots. No drive, chat cache, session
cache, or alternative-root search was performed. No target project protocol
bytes were changed.

The first AUDAPACK path supplied by the operator omitted the leading underscore.
That failed binding and remains recorded in the earlier historical preflight.
This acceptance uses the corrected exact repository root.

## AUDAPACK

- exact_root: `V:\___VAC\__K\__CODE\_PY\_AUDAPACK`
- project_identity: `v:\___vac\__k\__code\_py\_audapack`
- project_lineage: `lineage-79944d6c0334416ebe1001e97de6c1cc`
- classification: `BOUND_RECOVERY_REQUIRED_BLOCKED`
- reason_code: `RECONCILE_REAUTH_REQUIRED`
- needs_local_mutation: `false`
- safe_auto_repair_available: `false`
- operator_decision_available: `true`
- canonical_next_command: `saipen recover resolve-blocker "<decision>"`
- read_only: `true`
- blocking_surface: `state`
- blocking_field: `blocker`
- evidence_reference: `.saipen/STATE.md`
- router result: `saipen status`, reason `unblock`, behavior
  `RESTATE_AND_STOP`

Disposition: the blocker is a genuine operator gate. It was not cleared. The
operator-decision command is reachable and exact; ordinary Work remains
blocked. Product Work and lifecycle state were not changed and no DONE claim
was made.

## SAITULS

- exact_root: `V:\___VAC\__K\__CODE\__SAITULS`
- project_identity: `v:\___vac\__k\__code\__saituls`
- project_lineage: `lineage-ded945ae8243480ab1bfee73baeb29c6`
- classification: `BOUND_RECOVERY_REQUIRED_BLOCKED`
- reason_code: `HISTORY_LEDGER_CORRUPT`
- terminal_disposition: `FORENSICALLY_UNRECOVERABLE`
- needs_local_mutation: `false`
- safe_auto_repair_available: `false`
- operator_decision_available: `false`
- canonical_next_command: `null`
- read_only: `true`
- blocking_surface: `log`
- blocking_field: `null`
- evidence_reference: `.saipen/LOG.md`

Disposition: malformed immutable events at `LOG.md:1318`, `LOG.md:1319`,
`LOG.md:1320`, and `LOG.md:1322` make historical truth unreconstructable.
Recovery does not synthesize, delete, or rewrite ledger history. The legacy
`parked_work` STATE residue remains separately visible to the read-only `next`
projection, but immutable-ledger failure correctly prevents any local mutation.
There is no `needs_local_mutation=true` deadlock.

## FastPrompter

- exact_root: `V:\___VAC\__K\__CODE\_PY\_FastPrompter`
- project_identity: `v:\___vac\__k\__code\_py\_fastprompter`
- project_lineage: `lineage-c13f771bc2924a5a81b65fc79e5aca08`
- classification: `BOUND_RECOVERY_REQUIRED_BLOCKED`
- reason_code: `RECONCILE_REAUTH_REQUIRED`
- terminal_disposition: `RECOVERY_BLOCKED`
- needs_local_mutation: `false`
- safe_auto_repair_available: `false`
- operator_decision_available: `false`
- canonical_next_command: `null`
- read_only: `true`
- blocking_surface: `state`
- blocking_field: `next_action`
- evidence_reference: `.saipen/STATE.md`

Disposition: the freeform `next_action` cannot be projected because HUNT is not
ticket-bearing and `task` is narrative rather than a Work id. The `(empty)`
BOARD residue and legacy `evidence:` field remain visible in the read-only
checkpoint diagnostic. No canonical edit or guard bypass is permitted. The
pre-fix `Fleet -> bare recover -> same refusal` loop is replaced with a precise
non-mutating terminal result.

## Regression closure

The live run exposed one T-1324 defect: terminal historical/ambiguous truth was
incorrectly advertised as an operator decision with bare `saipen recover`, even
though that command could only repeat the same refusal. The repair preserves the
existing T-1324 remediation vocabulary and adds a closed terminal disposition:

- `FORENSICALLY_UNRECOVERABLE` for immutable-ledger corruption;
- `RECOVERY_BLOCKED` for ambiguous truth with no lawful local reconstruction.

Both require `needs_local_mutation=false`, expose no canonical mutation command,
retain `READ_ONLY_DIAGNOSIS_ONLY`, and enumerate forbidden probes. Deterministic
repair and real operator-decision cases retain their exact existing commands.
