# FUTURE GATE — RECONCILE DEADLOCK: UNAPPLIABLE DETERMINISTIC REPAIR + UNROUTABLE DONE-WITHOUT-VERIFY

Status: RECORDED FOLLOW-UP WORK / NOT AUTHORIZED FOR IMPLEMENTATION

Recorded: 2026-09-17 by an opencode session bound to `_FastPrompter`
(`V:\___VAC\__K\__CODE\_PY\_FastPrompter`), lineage
`lineage-c13f771bc2924a5a81b65fc79e5aca08`, actor `buffy`, protocol `8.0.1`,
source_head `10a298979f9c8050ff82551d5870339350b9c1a9`.

This document is a record of an external, mechanically reproduced defect. It is
not a claim that anything here has been fixed, and it must not be cited as
evidence for any coverage disposition. Do not implement it while an active
ticket holds this repository's DOING seat.

The initial operator handoff was captured as ingress receipt `SRC-015` by
`saipen start --file` — which itself then refused with `WAIT_OPERATOR` pointing
back at the blocked repair below.

## DEADLOCK — TWO SANCTIONED REPAIRS EACH REQUIRE THE OTHER (P1)

A project carrying BOTH (a) a current-generation `## DONE` record with no
`| verify:` evidence and (b) an INVALID half claim pair on the active DOING
ticket has NO canonical exit. Each sanctioned repair is blocked by the other
defect, and the operator is walked in a circle.

`saipen validate --json` on the bound project returns 7 errors (excerpt):

```
FLOOR: STATE.task=T-1269 but BOARD DOING has multiple openers at the raw floor
BOARD proposed has more than one ## DOING ticket
BOARD proposed T-1269 has an open [ ] checkbox under ## DOING
BOARD proposed T-1270 has an open [ ] checkbox under ## DOING
BOARD proposed T-1260 is checked [x] but sits under ## TODO
BOARD proposed T-1268 sits under ## DONE with no | verify: evidence
## DOING T-1269 carries an INVALID claim (half owner/claim_time pair or non-UTC stamp)
```

Six of the seven are the deterministic drift `saipen recover` owns. The seventh
(T-1268) is a semantic record defect that `recover` does NOT list as a repair.

### Leg 1 — `recover --apply-approved-repair` refuses because of the defect it does not own

`saipen recover` plans the six drift repairs and returns
`RECONCILE_REAUTH_REQUIRED` with
`canonical_next_command: saipen recover --apply-approved-repair <repair_id>`.
Applying it fails fast validation:

```
REFUSE [VALIDATION_FAILED]
proposed reconciliation fails fast validation: BOARD proposed T-1268 sits under
## DONE with no | verify: evidence -- ## DONE is a claim that the ticket's own
verify condition was met
```

The proposed BOARD is rejected on an error that is OUTSIDE the repair plan. The
repair set is atomic, so one unowned error vetoes every repair it DID own —
including the claim-clear that leg 2 needs.

### Leg 2 — `ticket verify` (the only verb that can add `| verify:`) is blocked by the half claim

The only canonical operation that writes a `verify:` field is
`saipen ticket verify <T-###> <text>`. It never returns a structured Result: it
raises, because `_seat_agent` validates the BEFORE ownership snapshot and the
active DOING ticket carries the INVALID half pair:

```
saipen ticket verify T-1268 <text> --dry-run --json
Traceback (most recent call last):
  File ".../tools/saipen.py", line 7255, in main
    result = ticket_verify(
  File ".../saipen_engine/operations.py", line 4626, in ticket_verify
    "agent": _seat_agent(state, docs["board"].text_norm, agent),
  File ".../saipen_engine/operations.py", line 477, in _seat_agent
    raise OwnershipSplitError(split)
saipen_engine.operations.OwnershipSplitError: pre-existing INVALID active
ownership (half owner/claim_time pair or non-UTC stamp) -- execution ownership
is unreadable; repair before any non-transferring mutation
```

### Leg 3 — `claim` cannot take over to clear the half claim

```
saipen claim T-1269 --dry-run --json
{"ok": false, "code": "VALIDATION_FAILED",
 "detail": "T-1269 carries an INVALID claim (half owner/claim_time pair or
            non-UTC stamp); repair before claiming"}
```

`saipen claim T-1270` returns the same shape. `ticket compact T-1268` refuses
("already within the 1200-character BOARD cap") and so reaches nothing.

### The cycle

```
recover --apply-approved-repair  -> REFUSE: T-1268 has no | verify:
ticket verify T-1268             -> REFUSE: T-1269 claim INVALID (traceback)
claim T-1269                     -> REFUSE: T-1269 claim INVALID
clear T-1269 half claim          -> only reconcile owns it
reconcile                        -> blocked by T-1268
```

Every command named by the previous refusal is itself refusable. `recover`'s
`instruction` field insists `READ_ONLY_DIAGNOSIS_ONLY ... the only sanctioned
mutation is saipen recover --apply-approved-repair <id>` and lists `saipen
ticket` as a forbidden probe — while that one command provably cannot commit.
This is the T-1324 forbidden combination: `needs_local_mutation: false` and
`safe_auto_repair_available: false` while every canonical repair refuses and the
only remaining exit is manual BOARD surgery.

## SECONDARY DEFECT — ERROR NORMALIZATION GAP ON THE VERIFY PATH

`ticket verify` is the one operation that escapes as a Python traceback
(`OwnershipSplitError`) instead of a structured `Result` with a stable code and
a `canonical_next_command`. Every sibling mutating operation catches the same
precondition and returns `VALIDATION_FAILED`. A weak agent reading a traceback
has no stable code to branch on and no named next action — the exact
`ERROR_NORMALIZATION_GAP` lens in `SAICRITIC.md`.

## BOUNDED FOLLOW-UP OPTION

Two independent changes, each separately red-controlled:

1. **Do not let an unowned BOARD error veto an owned repair plan.** Either make
   `recover`'s fast-validation of the proposed surface evaluate only the
   invariants the repair plan actually owns, or add the DONE-without-verify
   reconstruction to the repair set so the same atomic pass can commit it. The
   latter is preferable only if reconstructing verification evidence from the
   existing closure LOG event (`E-1935` here: `RUN: VERIFY -> PASS`) is judged
   canonical rather than fabricated — the engine already refuses to invent
   evidence, so this is a semantic decision, not a mechanical one.
   Alternative minimum: have `recover` REFUSE up front with a structured code
   naming the unowned error and the one verb that owns it, instead of returning
   an apply-command that cannot commit.

2. **Normalize the verify path.** `ticket_verify` must catch the invalid-active
   ownership precondition and return a structured `Result` (same predicate,
   same words as `_seat_agent`), never a traceback, so the refusal names a
   reachable next action.

Required hostile controls:

- A project with a current-generation `## DONE` record lacking `| verify:` AND
  an INVALID half claim on the active DOING ticket reaches a canonical terminal
  state through named commands only; a red control on the current code shows the
  3-leg cycle exactly as above.
- `saipen ticket verify T-### <text>` against an INVALID active claim returns a
  stable `Result` code (no traceback), and the code is one an operator can act
  on.
- A deterministic repair plan still refuses to commit a surface carrying an
  error it did not repair — the veto must not be removed, only made
  non-circular.

NON-GOALS: do not weaken the `## DONE requires | verify:` invariant; do not
fabricate verification evidence; do not add a generic "unblock anything" verb;
do not advise manual BOARD.md edits — the whole point is that protocol state
changes through operations.

## MINIMAL REPRO

```
mkdir scratch/.saipen
# STATE: phase SCOUT, task T-2, agent X
# BOARD:
#   ## DOING
#   - [ ] T-2 [P1] ... | owner: X            <- owner, no claim_time
#   ## DONE
#   - [x] T-1 [P1] ... (no | verify:)
saipen validate --json        # 2 errors: T-2 INVALID claim, T-1 no verify
saipen recover                # RECONCILE_REAUTH_REQUIRED + apply command
saipen recover --apply-approved-repair <id>
                              # REFUSE: T-1 sits under ## DONE with no verify
saipen ticket verify T-1 x    # Traceback: OwnershipSplitError
saipen claim T-2              # REFUSE: INVALID claim; repair before claiming
```

## ORIGINATING MISSION

Operator handoff `FastPrompter_20260917_1615.md` (continuation master append),
delivered to the bound `_FastPrompter` session as ingress receipt `SRC-015`.
The session could not begin the requested work because the project's protocol
state is in the above deadlock; no implementation file was touched. The fix
belongs to the SAIPEN protocol tree, a different repository than the bound
project, so this record is the cross-project handoff rather than an edit of
unrelated protocol code.
