# FUTURE GATE — SHIP DEADLOCK ON UNRESOLVED ACTIVE SOURCE COVERAGE

RECORDED FOLLOW-UP WORK / NOT AUTHORIZED FOR IMPLEMENTATION
Recorded: 2026-09-12 by astra2 while closing T-1316 (SRC-027).
Status: STRUCTURAL FINDING — observed live, reproduced deterministically, not fixed.

Do not implement any change described here while an active ticket holds the
DOING seat. This file is evidence, not an authorization.

## WHAT HAPPENED

T-1316 (P0, SRC-027) reached SHIP with REVIEW verdict `DEC: SHIP`, every
pre-publication gate green, and an operator decision to close locally without
publishing. The canonical `no-publish` release refused:

```
REFUSE [RELEASE_FAILED]
  stage:  SOURCE_COVERAGE
  detail: active source receipt blocks ship:
          {'ok': False, 'code': 'SOURCE_UNRESOLVED', 'receipt': 'SRC-026',
           'work': 'T-1304', 'coverage': {... 'terminal': 4, 'UNKNOWN': 8,
           'unresolved': ['SRC-026:R005' ... 'SRC-026:R012']}}
```

Two independent, verified blockers — measured, not inferred:

| Receipt | Owner | complete | Evidence |
|---|---|---|---|
| SRC-026 | T-1304 (operator-PAUSED) | `False` | 12 actionable, 4 terminal, 8 `UNKNOWN` (R005–R012) |
| SRC-027 | T-1316 (this ticket) | `False` | 15 actionable, 14 terminal, 1 `DEFERRED` (R014) |

Measured with the engine's own authority, not by reading JSON:

```python
from saipen_engine import intake as I
I.coverage_summary(root, 'SRC-026')   # unresolved: R005..R012
I.coverage_complete(root, 'SRC-026')  # False
I.coverage_complete(root, 'SRC-027')  # False, unresolved: ['SRC-027:R014']
```

## WHY IT IS A CONTRADICTION, NOT A BUG IN T-1316

1. `intake.py:86` `TERMINAL_DISPOSITIONS` does **not** contain `DEFERRED`.
   `intake.py:1401` `coverage_complete()` is `actionable > 0 and not
   unresolved`, so `DEFERRED` reads as unresolved forever. A requirement that
   was deliberately, truthfully deferred to a follow-up is indistinguishable
   from one nobody has looked at. There is no honest way to record "known,
   owned, not done here" on a source receipt.
2. `intake.py:1677` `release_gate()` iterates **every** active receipt and
   requires `coverage_complete` for each. It is not scoped to the shipping
   ticket's own source. Therefore an ACTIVE receipt belonging to an unrelated,
   operator-paused ticket vetoes every other ticket's ship.
3. An operator-authorized P0 interrupt therefore **deadlocks its own closure
   path**. SRC-026 is ACTIVE *because* T-1304 was interrupted; T-1304 is
   prevented from resuming by T-1316's seat; and T-1316 cannot ship while
   SRC-026 is unresolved and active. Each leg is individually correct.
4. Documented-vs-runtime drift: `saipen/phases/ship.md`'s `mode: no-publish`
   table lists what runs as "board, README, version, junk, local metadata, core
   gate". Source coverage is **not** in that table, and the phase text says
   no-publish performs zero staging/commit/tag/push. The runtime nevertheless
   runs `release_gate()` in `release.py` APPLY before the `no-publish` branch
   (`release.py:1891` precedes `release.py:1943`), so a no-publish local
   closure is gated by a check its own phase document does not claim.

Reproduce the refusal without publishing anything:

```bash
SAIPEN_CAPABILITY=no-publish python tools/saipen.py ship --json
```

## HOW T-1316 STOPPED (for the record)

Per the mission's STOP CONDITION, T-1316 did **not** resolve the contradiction
by touching protocol semantics, by adjudicating SRC-026 (another ticket's
coverage), or by promoting `DEFERRED` to a terminal value. It blocked itself
with the exact facts:

```
saipen ticket block T-1316 "<two verified blockers>" --scope ticket
```

Result: T-1316 in `## BLOCKED`, `blocker_scope: ticket`, LOG E-6027, DOING seat
empty, STATE `phase: DONE / task: none`. The verified recovery work itself is
untouched and remains green.

## BOUNDED FOLLOW-UP OPTIONS (choose ONE per ticket, later)

Each option changes exactly one semantic authority family. Do not implement all
of them as one change, and do not weaken source coverage to save a release.

1. **A terminal disposition for owned, deferred work.** Give the coverage model
   an honest non-terminal-but-adjudicated state, or make `DEFERRED` carry a
   mandatory owner + follow-up ticket so `coverage_complete` can distinguish
   "owned deferral" from "unexamined". Hostile control: an unowned or
   ticket-less `DEFERRED` must still block ship; `UNKNOWN` must still block.
2. **Scope the release gate to the shipping ticket's own sources.** A release
   should be blocked by ITS OWN unresolved coverage, and by any receipt whose
   linked Work is DONE-but-unclosed; it should not be blocked by an unrelated
   ticket's in-flight source. Hostile control: a *DONE* Work with an unresolved
   receipt, and an active receipt whose linked Work is the shipping ticket,
   must both still refuse.
3. **Reconcile `ship.md`'s `no-publish` table with the runtime.** Either list
   source coverage among the checks a no-publish closure still performs, or
   make the runtime honour the table. Hostile control: no-publish must never
   become a bypass past source coverage for the ticket's own sources.

NON-GOALS: no weakening of `coverage_complete`; no auto-adjudication of another
ticket's requirements; no fabricating terminal dispositions to clear a release;
no `-publish` flag that skips the gate; no historical LOG/BOARD rewrite.

## SECOND FINDING SURFACED BY THE BLOCK — T-1293's CLASS, VIA A NEW DOOR

Blocking T-1316 emptied the DOING seat. STATE then read `phase: DONE /
task: none` and the engine routed `next_action: PHASE SCOUT T-1315`, while the
ACTIVE audit layer 16 (SRC-026 / T-1304) still routes `PHASE SCOUT T-1304`.
The validator refuses:

```
FAIL: STATE.md audit route not followed -- the audit inbox routes
      'PHASE SCOUT T-1304' (layer 16, audit/16.md) but next_action is
      'PHASE SCOUT T-1315'
```

This raised the tree from 21 to 22 validator problems. It is the documented
T-1293 contradiction ("audit route vs a legal continuation next_action")
reached through a different door: while ANY ticket was DOING, its continuation
satisfied the audit-route check, so the defect was invisible. The moment the
seat is legitimately empty, the router's only workable pick (T-1315, since
T-1304 is blocked/PAUSED) and the audit layer's mandated route become
unsatisfiable together.

T-1293 already owns that class. Do not fix it here and do not route around it
by hand-editing `next_action`. Recorded because a truthful BLOCK now
mechanically produces a validator red, which is a property of the router, not
of the blocked ticket.
