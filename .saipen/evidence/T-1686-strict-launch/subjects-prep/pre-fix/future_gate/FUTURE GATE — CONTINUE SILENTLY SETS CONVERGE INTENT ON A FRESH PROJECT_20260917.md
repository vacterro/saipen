# FUTURE GATE — `continue` SILENTLY SETS CONVERGE/DONE INTENT ON A FRESH PROJECT

Status: RECORDED FOLLOW-UP WORK / NOT AUTHORIZED FOR IMPLEMENTATION

Recorded: 2026-09-17 by a claude session binding the greenfield project
`V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\__SAIMAIL__`
(lineage `lineage-3172dbca95fc4945955bdee3acff8d75`), reproduced three times on
two throwaway roots against installed protocol `8.0.1` and
`_SAIPEN/tools/saipen.py` at `source_head 10a298979f9c8050ff82551d5870339350b9c1a9`.

Companion record to `FUTURE GATE — GREENFIELD BIRTH HAS NO MECHANICAL
OPERATION_20260917.md`; the two were found in the same bind. Not a claim that
anything is fixed, not usable as coverage evidence. Do not implement while an
active ticket holds this repository DOING seat.

## DEFECT — FIRST `saipen continue` REWRITES `execution_intent` WITHOUT BEING ASKED (P1)

On a freshly born, validator-clean project sitting at a `WAIT:`, the first
`saipen continue --json` returns the wait correctly AND, as a side effect,
writes `execution_intent: converge` + `converge_target: done` into STATE and
logs `E-1 DEC: execution intent -> converge/done`.

Nobody requested converge. The project had no history, no DOING, no closed
work — nothing that could have implied a convergence goal.

Reproduced, each command run alone against a scratch root and STATE hashed
before and after:

```
BASE md5=ce2a603489c0afbc168d273d772c2139
after validate: UNCHANGED  log_bytes=7
after status:   UNCHANGED  log_bytes=7
after continue: CHANGED    log_bytes=139
```

STATE before: `execution_intent: normal`, no `converge_target`, no
`last_event`. STATE after:

```
execution_intent: converge
converge_target: done
last_event: 1
```

LOG after:

```
- 17.09.26 08:53 [E-1] [agent: claude] [op: converge_intent-64cbd65730674739b31ddf934348fc9b] DEC: execution intent -> converge/done
```

Variants tested:

- `execution_intent: normal` present -> flipped to converge/done.
- `execution_intent` field absent entirely -> converge/done written in.
- Empty BOARD -> flipped. BOARD carrying one workable `## TODO` ticket ->
  flipped identically, `reason` still `wait`.
- One-shot, not a loop: two further `continue` calls added no second event
  (`grep -c converge_intent` -> `1`, `last_event: 1`).

`validate` and `status` are clean in every variant; the mutation belongs to
`continue` alone.

## WHY THIS MATTERS MORE THAN A STRAY FIELD

1. `BOOT.md` step 6 says a persisted `WAIT:` is returned verbatim. It is — but
   the router does not get to repaint the execution intent on its way past. A
   read of the router is being charged as a decision by the project.
2. `converge_target: done` is precisely the value that, per the recorded
   `FUTURE GATE — CLAIM PATH OVERSIZE AND IDLE CONVERGE ROUTING_20260916.md`
   (DEFECT B), has NO idle branch in the router: only `converge_target == crew`
   is implemented, and `done`/`ship` fall through to the Improve path while
   `CONVERGE.md` line 22 and `MAINTENANCE.md` 2.1 promise the converge stages.
   So the first router read of a newborn project parks it in the one intent
   whose idle route is already recorded as broken.
3. The first event in a project history is now a decision the project never
   made. Every later audit that reads `E-1` as intent provenance reads an
   artifact of routing.
4. A seat that later reports "this project is converging" is telling the truth
   about STATE and nonsense about the work — narrative authority leaked from a
   side effect, the exact class `KNOWLEDGE/cards/narrative-authority-leakage.md`
   exists to catch.

## BOUNDED FOLLOW-UP OPTION

1. Find the writer (the `converge_intent-*` operation raised on the `continue`
   path) and make intent changes require an explicit intent-bearing verb.
   `continue` reads the route; it does not author intent.
2. If some converge default is genuinely wanted for a cold project, it must be
   an explicit, documented, and logged decision with a stated reason — and it
   must not pick a `converge_target` whose idle branch is unimplemented.
3. Ship a control for the first-router-read case specifically: a project whose
   entire history is one event caused by reading the router is a provenance
   defect, not a checkpoint.

Required hostile controls:

- Fresh valid project at a `WAIT:`: `saipen continue --json` returns the wait
  and STATE bytes are identical before and after; the red control on current
  code shows `execution_intent: converge` + `converge_target: done` + `E-1`.
- Same for a project carrying a workable TODO (the flip is not empty-board
  specific).
- Intent verbs keep working: an explicit converge request still writes intent
  and still logs it.
- No silent repair: a project already carrying the injected converge/done is
  not rewritten behind the operator's back either. The fix stops the write; it
  does not start a second one.

NON-GOALS: do not remove `execution_intent` from STATE; do not make `continue`
refuse on a missing intent field; do not hand-edit affected projects out of
band — the whole point is that protocol state changes through operations.

## COLLATERAL IN THE FIELD

`__SAIMAIL__` itself now carries `execution_intent: converge` /
`converge_target: done` / `E-1` from this defect, written before its first
ticket existed. It was deliberately NOT hand-repaired: manual STATE surgery is
the failure mode the protocol forbids, so the wrong state stays visible until a
canonical operation can correct it. Treat that project as an in-the-wild
specimen rather than a clean baseline.

## ORIGINATING MISSION

Greenfield bind of `__SAIMAIL__` on 2026-09-17, during the first router read
after INIT. The fix belongs to the protocol tree, a different repository than
the bound project, so this record is the cross-project handoff rather than an
edit of unrelated protocol code.
