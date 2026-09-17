# T-1382 -- the repair was there; the reader stood in front of it

Measured 2026-09-17/18, protocol 8.0.1, SAIPAL shape rebuilt as a disposable
fixture (phase DONE, transition_from VERIFY, no active-block DEC at or before
`last_event`, nothing in BOARD.BLOCKED).

## RED -- every verb, including the repair verb

    status                      ok=False  VALIDATION_FAILED   next=
    next                        ok=False  VALIDATION_FAILED   next=
    continue                    ok=False  VALIDATION_FAILED   next=
    recover                     ok=False  VALIDATION_FAILED   next=
    validate                    ok=False  VALIDATION_FAILED   next=
    claim T-042                 ok=False  VALIDATION_FAILED   next=
    transition BUILD            ok=False  VALIDATION_FAILED   next=
    checkpoint RUN T-042 probe  ok=False  VALIDATION_FAILED   next=
    start 'a new task'          ok=False  VALIDATION_FAILED   next=

Nine verbs, one answer, no route. `status` additionally answered
`action: "saipen status"` -- the command that had just refused.

## The two defects

1. `operations._read` raised `state-history-binding` unconditionally, and
   `reconcile` reads through that same function. `_state_phase_repairs` has
   derived the correct pair from the transition chain since T-1318 and sat on
   the far side of the raise. A repair nobody can reach is not a repair.

2. `router.route_next` answered an invalid checkpoint surface with
   `action: "saipen status"`. A session reads `action` as an instruction, runs
   it, and gets the same refusal with the same instruction.

## GREEN -- same fixture, current bytes

    status                      ok=False  VALIDATION_FAILED   action=saipen recover
    recover                     ok=False  RECONCILE_REAUTH_REQUIRED
                                next=saipen recover --apply-approved-repair c861e793...
    continue                    ok=False  RECONCILE_REAUTH_REQUIRED   (same route)
    start 'a new task'          ok=False  WAIT_OPERATOR               (same route)

    apply                       ok=True   REPAIRED
    repaired STATE              phase: VERIFY   transition_from: BUILD
    validate                    VALID
    recover                     CLEAN
    status                      ok=True   phase=VERIFY  next=saipen continue
    continue                    ok=True
    apply again                 STALE_APPROVED_REPAIR

`VERIFY`/`BUILD` are not a guess: E-003 proves the destination and E-002 the
source, from the project's own history.

## The invariant, and the boundary it does not cross

`operations.REPAIR_OBSERVABLE` is the closed set of damage classes a repair
planner may LOOK at: `state` (T-1318), `log` (T-1356), `history_binding`
(this). Everything else -- ledger corruption, dead home, history ownership,
every protected-path and seat gate -- stays armed for every caller.

Observation is not authority. Strict `_read` still raises for every ordinary
caller; the repair still needs an explicit `--apply-approved-repair <digest>`;
and while the damaged shape is observable, `transition`, `checkpoint` and
`claim` all still refuse and the STATE bytes are unchanged. Pinned by
`UnboundHistoryDeadlockTests.test_observing_damage_is_not_authority_to_mutate`.

## Regression

`tools/test_recovery_reachability.py::UnboundHistoryDeadlockTests`, 5 controls:
the strict reader still refuses, the observer sees the verdict, `recover` names
one command, the route converges and is idempotent, the original bytes survive
as recovery evidence, and observing is not authority.

    tools.test_recovery_reachability                      Ran 68   OK
    routing + recovery families (12 modules)              Ran 316  OK

---

# Specimen B -- _SAITULS: repairs that each needed another one's surface

Four damaged surfaces in one project: STATE carrying the retired output-only
field `parked_work`; three LOG lines that lost their leading `- ` plus one free
text line with no event tag; BOARD with a duplicate ticket id and two DONE rows
still carrying `blocker:`.

## RED -- individual repairs, no ordering

    validate  ->  ONE defect reported: unknown STATE field 'parked_work'
    recover   ->  names a repair; applying it is refused for five defects it
                  never proposed to touch
    normalize-log -> refused: needs a STATE the STATE repair had not made valid
    BOARD rows    -> unaddressable: two records under one id

Three defects sat between the repairs and each other:

1. **The allocator reused a spent id.** `tail` counted only PARSABLE events, so
   the malformed lines' `[E-1300]`/`[E-1301]` were free -- the repair minted a
   duplicate, and once that was fixed, a GAP, and refused its own proposal.
   An id a damaged line CLAIMS is spent. Now honoured in all three places that
   ask: the tail, the consecutive check and parent existence.

2. **Every proposal was judged on the whole project.** A repair walks in on
   damage by definition. `fast_check.defect_delta` judges it on what it
   CHANGED; what it inherits is declared in the journaled receipt through
   T-1354's own mechanism, matched by defect SIGNATURE so a line shift cannot
   defeat the declaration. Introduced damage still fails, unchanged.

3. **The validator hid what the write gate refused.** A STATE the parser
   refused returned immediately, so `validate --json` reported one defect while
   the write path knew about eight. The state-dependent checks still stop; the
   BOARD and LOG ones now run, from the same two functions both paths call.

## GREEN -- one question, then three commands

    recover        OPERATOR_DECISION_REQUIRED
                   "two BOARD records claim the same ticket id. Decide which
                    record keeps the id and give the other one a free id..."
                   (asked once, and identically until it is answered)

    [operator renames the duplicate row]

    recover --apply-approved-repair ...   REPAIRED
    recover --apply-approved-repair ...   REPAIRED
    recover normalize-log                 LOG_NORMALIZED
    recover                               CLEAN

    validate   VALID
    status     ok, phase BUILD
    continue   ok  -> saipen claim T-176

## RECOVER CLEAN now means something

`recover` used to certify CLEAN while `validate` listed six defects and every
ordinary verb refused. CLEAN is a claim about the PROJECT, not about this
function's own repair set: what is left is reported as `RESIDUAL_DEFECTS` with
the command that owns it (`saipen recover normalize-log`) or, where no
canonical repair can choose, the one operator decision that unblocks the rest.

## What this does NOT do

Relaxing a READ never relaxed an AUTHORITY. Ordinary mutation still refuses on
a damaged project; the repairs still need `--apply-approved-repair <digest>`;
seat and ownership semantics are untouched; and a repair may not be aimed
THROUGH an unaddressable record, because line surgery on a duplicated id edits
whichever row the parser kept.

## Regression

`tools/test_recovery_reachability.py::CyclicRepairDependencyTests`, 6 controls:
validator parity, the one decision (asked once, never auto-repaired), the whole
sequence executable after it, idempotence with no loop, CLEAN as a project-wide
claim, and forensic preservation of every rewritten surface.

    tools.test_recovery_reachability                       Ran 74   OK
    recovery + routing + binding families (17 modules)     Ran 441  OK
    tools/validate.py                                      conformant
    ruff (tools/ tests/)                        1 pre-existing E501 in the
                                                unowned foreign delta (T-1389)

---

# The stranded claim (AUDAPACK) -- a repair that existed and nothing named

`STATE.task` names Work that `## DOING` does not hold.

## RED

    start            refused, and pointed at itself
    start --receipt  refused, and pointed at itself
    status           invalid
    recover          CLEAN
    saipen claim T-188   repaired the floor in one command

Two separate failures in one shape: a diagnostic surface certifying a project
the write gate refuses, and a route pointing back into the refusal that
produced it.

## GREEN

    status     VALIDATION_FAILED   action=saipen recover
    recover    RESIDUAL_DEFECTS    next=saipen claim T-188
               residual: STATE.task=T-188 but BOARD DOING is empty at the raw
                         floor; STATE proposed phase SCOUT is ticket-bearing
                         but BOARD has no ## DOING ticket
    continue   RESIDUAL_DEFECTS    next=saipen claim T-188
    start      WAIT_OPERATOR       next=saipen claim T-188

    saipen claim T-188   CLAIMED
    validate   VALID      recover  CLEAN      status ok      continue ok

The shortcut is scoped to a CLAIMABLE record. A `task` naming a `## DONE` row
has two legitimate answers -- reopen it, or clear the field -- so it gets no
`claim` route at all; the phantom-DONE owner asks for its own approval instead.
Guessing between two legitimate meanings is the thing this ticket exists to
stop, and the test pins that it does not happen.

    tools/test_recovery_reachability.py::StrandedClaimTests   4 controls
