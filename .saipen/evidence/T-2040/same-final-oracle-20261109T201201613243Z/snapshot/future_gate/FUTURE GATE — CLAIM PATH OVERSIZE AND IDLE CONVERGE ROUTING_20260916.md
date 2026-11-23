# FUTURE GATE — CLAIM-PATH EXTERNALIZATION GAP AND IDLE CONVERGE ROUTING

Status: RECORDED FOLLOW-UP WORK / NOT AUTHORIZED FOR IMPLEMENTATION

Recorded: 2026-09-16 by an opencode session bound to `_PROBLIP`
(lineage `lineage-1cdb16999979467cae251752806324f5`), from improve cycle
`imp-vacterro-problip-20260916-1` RUN-1 (IMP-001, IMP-002), CONFIRMED and
reproduced live at HEAD 295492a.

This document is a record of an external, mechanically reproduced defect. It is
not a claim that anything here has been fixed, and it must not be cited as
evidence for any coverage disposition. Do not implement it while an active
ticket holds this repository's DOING seat.

## DEFECT A — CLAIM PATH MISSES THE T-1326 PHASE-3 EXTERNALIZATION (P1)

T-1326 TARGET B promises that a normal BOARD row which crosses the live
1200-char cap BECAUSE of a requested mutation completes canonically by
externalizing the grown row. The claim path does not implement that leg.

- `tools/saipen_engine/operations.py` `_plan_claim` calls only
  `prepare_existing` (pre-mutation compaction of an ALREADY-oversized row) and
  never `prepare_expanded`. `_project_board_mutation` (same file, ~line 829)
  runs BOTH: phase-1 `prepare_existing` + phase-3 `prepare_expanded`.
- `_claim_move` adds `owner` + `claim_time` via `set_ticket_field` with the
  default `enforce_cap`, so the overflow is raised there with no externalization
  stage behind it.

Observed live: a legal `## TODO` ticket (T-17) whose own description + verify
field already sat near the cap refused on claim:

```
REFUSE [BOARD_RECORD_OVERSIZE]
  new/updated live ticket record is 1220 characters, cap is 1200
```

followed by:

```
saipen ticket compact T-17
REFUSE [VALIDATION_FAILED]
  T-17 is already within the 1200-character BOARD cap
```

No canonical verb reached the row. `ticket compact` measures the PRE-claim
record (under cap) and refuses; `claim` measures the POST-field record (over
cap) and refuses. The only exit was manual field truncation — the precise
T-1324 forbidden combination (`needs_local_mutation: true` while every
canonical repair refuses).

## DEFECT B — IDLE CONVERGE ROUTES TO IMPROVE INSTEAD OF THE CONVERGE STAGES (P2)

Under `execution_intent: converge` / `converge_target: done` with a halted board
(empty `## DOING` + `## TODO`), the contract says one thing and the engine does
another.

- `saipen/CONVERGE.md` line 22: "Absent or `done` is plain `cc`: run A-M."
- `saipen/MAINTENANCE.md` §2.1: "a halted board enters HUNT without asking ...
  Under converge it routes by CONVERGE stages F/I and MUST NOT enter ADD."
- Engine: `tools/saipen.py` (~line 1685) fires `fallthrough_to_improve`
  whenever `_is_idle_maintain_route` holds (`action: saipen continue`,
  `reason: maintain`) with no converge-target branch.
  `tools/saipen_engine/router.py` (~line 407) implements a converge branch ONLY
  for `converge_target == "crew"`; `done` and `ship` have none.

Observed live: on a converge/done project with an empty BOARD, `saipen continue
--json` returned `{code: IMPROVE_AUDIT_ASSIGNMENT}` and admitted improve cycle
`imp-vacterro-problip-20260916-1`, while `saipen status --json` reported
`convergence_current: false` and `closure_complete: false` with
`execution_intent: converge` still set. The CONVERGE closure bar (E test gate,
F forced HUNT, G CLEAN, H post-clean test, I final HUNT, + J-M factory
freshness) is unreachable through routing for `converge/done`. (The improve
fallthrough itself is documented for the normal/goal idle case in
`CMD-CONTINUE-01`; the gap is that converge/done does not get its own branch.)

## BOUNDED FOLLOW-UP OPTION

Two independent, separately red-controlled changes:

1. `_plan_claim`: run the grown row through `prepare_expanded` exactly as
   `_project_board_mutation` does, adding its detail targets to the same
   journaled plan.
2. Routing: give `converge_target in (done, ship)` an idle branch that
   continues the CONVERGE sequence (stage F forced HUNT, or stage E test gate)
   instead of the Improve fallback, or document by design why converge must
   also reach the improve fallthrough.

Required hostile controls:

- A claim on a real TODO row whose `owner`+`claim_time` push it past 1200 chars
  completes via externalization with the full record preserved in a detail
  artifact; a red control proves the pre-fix code refuses with
  `BOARD_RECORD_OVERSIZE` and `ticket compact` cannot repair it.
- A converge/done project with an empty BOARD routes `cc` to the CONVERGE
  continuation, not `IMPROVE_AUDIT_ASSIGNMENT`; a red control on the current
  code returns `IMPROVE_AUDIT_ASSIGNMENT`.

NON-GOALS: do not weaken `BOARD_RECORD_OVERSIZE`; do not remove the improve
fallthrough for normal/goal intent; do not fabricate convergence receipts.

## ORIGINATING MISSION

`_PROBLIP` improve cycle `imp-vacterro-problip-20260916-1`, seat `buffy-01`,
findings RUN-1/IMP-001 and RUN-1/IMP-002 (both CONFIRMED, reproduced). Spawned
as Problip ticket T-22. The fix belongs to the SAIPEN protocol tree, which is a
different repository than the bound project, so this record is the established
cross-project handoff rather than an edit of unrelated protocol code.
