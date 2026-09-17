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
