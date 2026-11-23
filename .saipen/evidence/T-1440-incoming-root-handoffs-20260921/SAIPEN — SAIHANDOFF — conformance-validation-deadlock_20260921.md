SAIPEN — SAIHANDOFF — conformance-validation-deadlock
SAIHANDOFF_V1
HANDOFF_ID: SAIHANDOFF-20260921-conformance-validation-deadlock
PROJECT_ID: lineage-b512942bac884a8691f6c98afcd6ddb9
PROJECT_NAME: SAIPEN
TOPIC: conformance-validation-deadlock
KIND: protocol-defect-report
ROLE: protocolist
TARGET_POLICY: reuse
DELIVERY: manual
CONTENT_SHA256: TBD-BY-MAINTAINER
END_HEADER

# SAIPEN — SAIHANDOFF — conformance validation deadlock

Status: RECORDED FOLLOW-UP WORK / NOT AUTHORIZED FOR IMPLEMENTATION

Recorded: 2026-09-21 by an opencode session bound to Wintage
(`V:\___VAC\__K\__CODE\_TAMPERMONKEY\_WIN95THEME\Wintage`), lineage
`lineage-30ee844c69d34eb68605a4563cfdb8ff`, actor `antigravity`, protocol
`8.0.1`, source_head `82178cd`.

This document is a record of a mechanically reproduced protocol loop plus the
bounded evidence gathered around it. Section "DIAGNOSTIC GAP" marks exactly
what was NOT proven from this session. It is not a claim that anything here
has been fixed, and it must not be cited as evidence for any coverage
disposition. Do not implement it while an active ticket holds this
repository's DOING seat.

Sibling classes (distinct, do not merge):

- FUTURE GATE — RECONCILE DEADLOCK ON DONE-WITHOUT-VERIFY PLUS INVALID ACTIVE
  CLAIM_20260917 (`future_gate/`): a DONE-without-verify + invalid-claim pair
  with no canonical exit. Overlaps the *shape* (a self-blocking remediation
  cycle) but was measured on a different fixture and names different legs;
  the current loop is `validate` remediating to `validate`.
- SAI-DEFECT-20260918-ship-source-coverage-deadlock (T-1399): release-gate
  freeze over unrelated blocked coverage. Different gate (ship/source), same
  family (a global condition with no per-ticket exit).
- RAPORT-SAIPEN-CONFORMANCE-TRUTH-20260919 (T-1412 window): conflicting-truth
  controls across status surfaces. Relevant if the current receipt/state
  disagree, but not measured here.

Consumer context: the Wintage T-283 terminal-fonts feature (lineage
`lineage-30ee844c69d34eb68605a4563cfdb8ff`) is CLOSED and verified in its
working tree; the defect below is protocol machinery, not feature work.

## DEADLOCK — `validate` REMEDIATES TO ITSELF (P1)

`saipen continue --json` in phase DONE with no active work returns:

```
code: CONFORMANCE_UNHEALTHY
action: saipen validate
conformance_status: CURRENT_FAIL
```

`saipen validate --json` launches the canonical validator, which exits 1 with
`Validation FAILED: 6 problem(s), 68 warning(s)`, emits a fresh CURRENT_FAIL
receipt, and returns:

```
code: CONFORMANCE_UNHEALTHY
canonical_next_command: saipen validate
```

Every iteration ends where it began: `continue` requires `validate`, and
`validate` fails while requiring `validate` again. There is no forward edge.

Pre-existing reverify receipts did not clear it:

- `saipen work reverify T-243` -> WORK_REVERIFIED
- `saipen work reverify T-244` -> WORK_REVERIFIED
- `saipen work reverify T-245` -> `REVERIFY_REUSED`, RV-000003,
  `PASS_WITH_CARRIED_DEBT` (68 warnings, `evidence_class: executed`)

The loop persisted unchanged after all three.

## DIAGNOSTIC GAP — the current blocking set is unproven from this session

`tools/saipen.py::_bounded_validator_output` keeps only the final 2000
characters of validator output for the `validate --json` summary. The full
problem list of the CURRENT run was not captured here; the debt snapshot below
is a prior generation's evidence and is cited only as a lead, not as the
current finding set.

Lead only (DEBT-000032, pre-BUILD T-283, 9 problems at that time):

- 2x saitranslate sub-board defects
- 1x structural-event-missing-op-marker (E-838)
- 3x `work_closure_evidence` — T-243/T-244/T-245 "no current-cycle VERIFY
  boundary; no current-tree PASS re-verification receipt"
- improve-report protocol fingerprint
- saihunt sub-write-boundary
- hunt commit on no remote branch

The CURRENT_FAIL receipt that owns the deadlock carries NO failing detail or
remediation list:

```
"receipt_id": "receipt-a81d4c5d7785",
"remediation_commands": [],
"canonical_next_command": "saipen validate",
"reason": "canonical validator reports FAIL for the current checkpoint"
```

An agent cannot distinguish which of the 6 current problems are stale, which
are ownerless, and which it may repair — and re-running `validate` is the only
named route.

## Candidate investigation directions (bounded; protocolist decides)

1. Break the `validate` -> `validate` fixed point. A remediation that names
   itself as the remedy is not a remediation; require a distinct,
   executable next command or an explicit external-ownership statement.
2. Surface the complete blocking findings on `validate --json`, not a
   2000-char tail. Either carry the structured findings (rule_id,
   subject, detail, finding_key) in the JSON block or emit the canonical
   findings artifact for the failing run. (The DEBT-000032 list above is a
   stale-generation lead, not the current evidence — first capture the live
   findings.)
3. Reconcile `PASS_WITH_CARRIED_DEBT` reverify receipts with the CURRENT_FAIL
   decision. If carried debt keeps the gate red, the reverify verdict must say
   so and name the owner; if it clears it, the decision must update.
4. Check stale conformance index/generation handling on this path — lead only:
   index `core.json` names a 2026-09-11 generation receipt while the active
   receipt is 2026-09-20. Unproven whether the live decision reads the stale
   entry.
5. Keep the read-only findings capture reachable when no work ticket is
   active. The guard currently refuses most tools at DONE/task-none, which
   blocks diagnosis of exactly this class of protocol defect.
6. Add red/green regression coverage for termination: a fixture in this state
   reaches a terminal report or a named external repair within a bounded
   number of `validate` iterations — never a self-loop.

NON-GOALS: do not weaken fail-closed validation; do not downgrade problems to
warnings; do not fabricate PASS receipts; do not mutate the Wintage consumer
while investigating.

## MINIMAL REPRO

```
# bound project: Wintage @ 82178cd, phase DONE, task none, E-1368
saipen continue --json
# CONFORMANCE_UNHEALTHY; canonical_next_command: saipen validate
saipen validate --json
# validator.exit_code: 1
# Validation FAILED: 6 problem(s), 68 warning(s)
# canonical_next_command: saipen validate
saipen work reverify T-243   # WORK_REVERIFIED
saipen work reverify T-244   # WORK_REVERIFIED
saipen work reverify T-245   # REVERIFY_REUSED, PASS_WITH_CARRIED_DEBT
saipen continue --json
# CONFORMANCE_UNHEALTHY; canonical_next_command: saipen validate
saipen validate --json
# identical CURRENT_FAIL; identical self-remediation
```

## ORIGINATING MISSION

Wintage T-283 (SRC-026): TERMINAL FONTS subsystem — 20 vendored monospace
families, canonical typography preference, private-font live preview,
data-driven third GUI tab, Windows Terminal + conhost apply driven by the
preference, focused suites with red controls, full Run-Tests.ps1 matrix green.
Closed E-1368 as own_patch. The deadlock above is what `cc` hit AFTER closure;
no product file was touched during diagnosis.
