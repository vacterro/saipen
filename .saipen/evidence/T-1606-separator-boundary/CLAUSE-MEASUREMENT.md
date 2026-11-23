# SRC-167 clause measurement for T-1606 closure

Every figure below was measured in this checkout on 2026-10-28, during SHIP.
Nothing here is inferred from a contract, a report or a prior run.

## R001 — WAIT_OPERATOR registered, no `unregistered_code`

`saipen/REGISTRY.json` `error_codes` is a 332-entry list; `WAIT_OPERATOR` is
member 1 of exactly one match. `saipen_engine.errors.CODES` is a frozenset of
the same 332 names and also contains it.

    Result(ok=False, code="WAIT_OPERATOR").to_dict()
    -> {"ok": false, "code": "WAIT_OPERATOR", "op_id": null, "changed_files": [],
        "recovery_required": false, "message": "wait"}
    Result(ok=False, code="TOTALLY_MADE_UP").to_dict()
    -> {... "code": "TOTALLY_MADE_UP", ... , "unregistered_code": true,
        "detail": "refusal code missing from REGISTRY.json error_codes"}

The marker is present for the unknown code and absent for `WAIT_OPERATOR`, so
the registration is load-bearing rather than incidental.

`tools/test_refusal_registry.py` — `Ran 6 tests in 6.926s ... OK`. That suite
includes `test_the_scan_actually_sees_the_measured_case`,
`test_a_code_named_through_a_module_constant_is_discovered` (the
`entry._decision_wait` case that made the code reachable while the registry
called itself complete) and `test_every_production_refusal_code_is_registered`.

The registration itself landed earlier, in `7949027c` (2026-10-27, under
T-1944/T-1945), not in this ticket. This run only re-measured it.

## R002 — one grammar at the construction boundary

Fixed in this ticket. Writer (`phases.phase_next_action_error`), strict reader,
checkpoint validation and reconciliation now share the `§ 1.6` enum guard via
`ALL_PHASES`; `tools/validate.py` imports the same constant and applies the
same guard. Pinned by
`test_the_validator_agrees_with_the_engine_on_every_verdict`, which AST-loads
the validator's own `_PHASE_NA_RE` and `_phase_next_action_error` and compares
verdicts over the unknowns plus all 16 enum phases.

Red control (`tools/test_next_action_deadlock.py`, validator guard removed):
`Ran 4 tests ... FAILED (failures=3)`, first failure naming `PHASE BANANA`.
Restored: `Ran 12 tests in 3.482s ... OK`.

## R003 / Control C / Control D — canonical WAIT round-trip

A scratch project (`saipen init`, `goal`, two tickets) was driven to a legal
`BLOCKED`/`task: none` shape carrying

    next_action: "WAIT: blocked -- operator must choose the probe path before any further work"

- `saipen status --json` -> `ok: true`, `phase: BLOCKED`, the WAIT string
  returned verbatim.
- `saipen continue --json` -> `ok: true`, `action: "saipen status"`,
  `reason: "unblock"`, `executable_behavior: "RESTATE_AND_STOP"`,
  `reconciliation: {"ok": true, "code": "CLEAN", "strict_state_error": null}`.

No `RECONCILE_REAUTH_REQUIRED` was produced. The WAIT payload was not executed:
`continue` answered a read-the-status route and `RESTATE_AND_STOP`, it did not
run the prose.

An earlier attempt at the same probe wrote `phase: BLOCKED` with `task: T-2`
and was refused — `STATE proposed phase BLOCKED is not ticket-bearing but task
is 'T-2'; task must be none outside a ticket-bearing phase`. That is the
grammar staying strict, not a WAIT defect.

## R004 / LEGACY STATE MIGRATION / Control F — bounded recovery

Same scratch project, `next_action` replaced with the freeform sentence
`phase blocked, someone should look at this`. Then:

- `saipen status --json` -> `VALIDATION_FAILED`,
  `reason: "checkpoint-invalid"`, and the detail quotes the offending value.
- `saipen recover --json` -> `ok: true`, `code: "REPAIRED"`, `repair_id
  fbc0a42c...`, `event E-7`, with the repair recorded as
  `classification: "NEXT_ACTION_CANONICALLY_PROJECTABLE"`,
  `from: "phase blocked, someone should look at this"`, `to: "saipen status"`,
  and `targets` including
  `.saipen/recovery/state-legacy-output/reconcile-20261028222523199458.STATE.md`.

The historical bytes survive in that snapshot and the current STATE becomes
valid. Nothing silently reinterpreted the prose as a command; the projection is
uniquely determined by the router for this checkpoint, and the operator gate is
retained whenever it is not.

## Control B — freeform at the writer

Measured directly against the canonical grammar:

    'operator: do something manually'                    refused=True
    'phase blocked, someone should look at this'         refused=True
    'PHASE NO_SUCH_PHASE'                                refused=True
    'PHASE banana'                                       refused=True
    'PHASE PLAN T-###'                                   refused=True

Persistence-level refusal was also observed live: a separator-bearing and a
freeform value both reached `VALIDATION_FAILED` before any write, the second
above as `STATE proposed next_action '...' does not start with
WAIT:/saipen /PHASE /RUN:/RESUME:`.

## Control E — valid forms unchanged

    'PHASE SCOUT T-1'                       accepted
    'PHASE BLOCKED'                         accepted
    'PHASE MARKHUNT'                        accepted
    'PHASE BUILD T-1 [12/40 files]'         accepted
    'PHASE DONE T-999'                      refused — T-### on a non-ticket-bearing phase

That last line is the pre-existing `§ 1.2` rule, unchanged by this ticket; it is
listed here because it is the control proving the gate did not widen.

## Control F — recovery command with spaces and punctuation

A value carrying quotes, a backslash-escaped comma and a semicolon
(`PHASE BLOCKED "quoted" \, and; punctuation!`) was persisted and then read:
`VALIDATION_FAILED` with the value quoted back intact, no truncation and no
argument splitting. The value reached the checker byte for byte, which is what
makes a rendered recovery command directly executable.

## R005 summary

Controls A, B, C, D, E and F were each exercised above. A, C, D and E also have
standing suites that were re-run here:

| Suite | Result |
| --- | --- |
| `test_refusal_registry` | `Ran 6 tests ... OK` |
| `test_recovery_reachability` | `Ran 85 tests in 40.353s ... OK` |
| `test_t1915_terminal_next_action` | `Ran 6 tests in 0.343s ... OK` |
| `test_t1572_ticket_scoped_recovery` | `Ran 18 tests in 19.470s ... OK` |
| `test_next_action_deadlock` | `Ran 12 tests in 3.482s ... OK` |
| `test_t1363_zero_manual_entry` | `Ran 75 tests in 62.287s ... OK (skipped=2)` |
| `test_t1729_gate_decision_lifecycle` | `Ran 15 tests in 7.644s ... OK` |
| `test_campaign_continuation_assessment` | `Ran 7 tests in 0.334s ... OK` |
| `test_t1739_wait_boundary` | `Ran 9 tests in 3.381s ... OK` |
| `test_t1880_wait_survives_phase_shortcut` | `Ran 3 tests in 0.642s ... OK` |
| `test_t1729_operator_gate` | `Ran 22 tests in 8.165s ... OK` |

The two skips in `test_t1363_zero_manual_entry` are capability skips, not
baselined regressions.

## R006 — declared family

`.saipen/evidence/core-unit/068d40626d14c9b0-20261028T220859747745Z.json`:
`status PASS`, `ran 8387`, `red []`, `jobs 1`, `duration_s 7954.5`,
fingerprint `068d40626d14c9b0bc50b901f40f5c311753728a7e69b8052500cb1814a5ddb1`.
That is the `--jobs 1` run, chosen because the sharded oracle is unstable (see
the risk note in REPORT.md).

## R007 — canonical lifecycle

T-1606 was claimed, blocked, unblocked with changed evidence, built, verified,
reviewed and shipped only through `saipen` verbs. No BOARD, STATE or LOG byte
was hand-edited in the Core tree. The scratch project used for the probes above
lives outside this checkout and is deleted after measurement.

## R009 — non-goals respected

No SAIPAL file was touched. No release root was added. The strict executable
grammar was narrowed, never weakened — Control E is the proof. WAIT payloads are
not executed (Control D). No authority was invented. Publication is excluded
per this clause and is therefore not part of this closure.
