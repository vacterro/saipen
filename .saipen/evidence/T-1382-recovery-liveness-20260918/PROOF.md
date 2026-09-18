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

Four damaged surfaces in one project, counted from the fixture rather than
from memory: STATE carrying the retired output-only field `parked_work`; FIVE
illegal LOG lines -- FOUR events (E-1300, E-1301, E-1302, E-1303) that lost
their leading `- ` plus one free-text line with no event tag; BOARD with a
duplicate ticket id and two DONE rows still carrying `blocker:`.

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

## GREEN -- one decision, then four commands, and zero file edits

    recover        OPERATOR_DECISION_REQUIRED
                   operator_decision: "...Decide which record keeps the id..."
                   duplicate_id_decision:
                     ticket  T-176
                     record 5bad16180f31  ## DOING  line 2  "[P1] the live one"
                     record 7e4b8198a60b  ## DONE   line 5  "[P1] the duplicate id"
                     choices: one exact command per candidate survivor
                   (asked once, and identically until it is answered)

    # the OPERATOR'S answer, carried by a canonical command:
    saipen recover --resolve-duplicate-id T-176 \
        --keep 5bad16180f31...  --reassign 7e4b8198a60b...
                   DUPLICATE_ID_RESOLVED   new_id=T-178 (allocator)

    recover --apply-approved-repair ...   REPAIRED
    recover --apply-approved-repair ...   REPAIRED
    recover normalize-log                 LOG_NORMALIZED
    recover                               CLEAN

    validate   VALID
    status     ok, phase BUILD
    continue   ok  -> saipen claim T-176

## What the decision carrier is, and what it is not

Before this, the engine's answer to a duplicated identity was a PROSE question
("give the other one a free id") and the only way to answer it was to edit
`.saipen/BOARD.md` -- a protected file the guard correctly refuses. The
decision is now CARRIED:

  * both records are named by CONTENT (`sha256` of the record's bytes), never
    by line number, because lines move and a decision that could be aimed at a
    different row is worse than no decision;
  * the operator decides WHICH record owns the historical identity. SAIPEN does
    not pick a survivor, and it does not ask the operator for the new id --
    `next_ticket_id` derives it over structured BOARD records and the complete
    LOG history;
  * only the record's IDENTITY TOKEN is renamed. References to the duplicated
    id elsewhere keep the survivor: a canonical rule cannot attribute them to a
    row that never owned the identity, and inventing that provenance is what
    the audit contract exists to catch;
  * one DEC records who decided what, and the exact BOARD bytes the decision
    was made against are preserved under
    `.saipen/recovery/board-duplicate-id/<op_id>/BOARD.md`;
  * it is ONE journaled plan/apply transaction (LOG + BOARD + STATE + evidence),
    so a crash after PREPARE converges through the ordinary replay.

Fail-closed boundaries, each pinned by a control:

    decision absent          -> OPERATOR_DECISION_REQUIRED, ZERO bytes written
    wrong/stale digest       -> STALE_DUPLICATE_ID_DECISION, ZERO bytes written
    line number instead of a digest -> VALIDATION_FAILED, ZERO bytes written
    same decision replayed   -> refused; no second record is renamed

A decision is bound to the RECORDS it names, not to the whole file: another
writer may append an unrelated row while the operator thinks, and that must not
invalidate a decision -- while a change to either named record must.

## Two delta rules this specimen forced

1. **Visibility.** A record dropped for a duplicated key is invisible to every
   semantic check (`parse_board` keeps the first record and files the rest as
   errors), so the second record's own stale blocker could not be reported
   whatever the repair did. The delta therefore measures its BEFORE side on the
   same board the proposal writes; the repair changes one identity token and
   nothing else, so the newly visible findings are inherited by construction,
   stay reported, and keep the project out of CLEAN until their own owner
   repairs them (`recover --apply-approved-repair`, measured above).

2. **Declared residue.** The post-write verifier exempts what the operation
   DECLARES (T-1354), matched by defect signature. The declaration here is
   `live findings + the delta's inherited set` -- sound because the delta has
   already established that the write introduces nothing (an introduced finding
   returns first), and pinned by controls proving an undeclared finding still
   fails and a declaration never exempts more than it names.

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

`tools/test_recovery_reachability.py::CyclicRepairDependencyTests`, 10 controls.
The GREEN route writes NO canonical file by hand: the decision is a canonical
command, and the fixture keeps its real multi-surface damage (FOUR bullet-less
events plus one free text line; a duplicate T-176; two stale blockers; the
retired `parked_work`).

    validator parity under malformed STATE        (4 independent defects)
    the decision names both records, by digest, with one exact command each
    nothing is written before the operator decides
    a wrong / stale / line-numbered decision is refused with zero writes
    ONE decision makes the whole sequence executable, and only one rename happens
    the renamed record differs in its identity token and nothing else
    the decision cannot be replayed
    idempotent: the route is never a loop
    CLEAN is a project-wide claim
    every rewritten surface's original bytes survive as evidence

`tools/test_defect_delta_controls.py`, 12 hostile controls: a defect that moves
line number is inherited; the same wording about another FILE is a new defect;
multiplicity is counted (two before/one after, one before/two after); the same
prose about another RECORD is a new defect (ticket ids are never normalized
away); removing its own defect keeps unrelated ones inherited; and the declared
residue exempts exactly what it names and nothing more.

    tools.test_recovery_reachability                       Ran 82   OK
    tools.test_defect_delta_controls                      Ran 12   OK
    recovery + routing + binding + guard families
      (30 modules, run in the session)                    Ran 843  OK
    tools/validate.py                                     conformant (30 warnings)
    ruff (T-1382-owned files)                             clean
    ruff (unowned foreign delta, T-1389)                  1 inherited E501
                                                NOT fixed and NOT counted here

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

---

# Core-unit attribution on the CURRENT bytes

The declared family is `python -m unittest discover -s tools -p "test_*.py"`
(`saipen_engine/test_runner.py`, declared timeout 600 s). Run whole it does NOT
finish inside 600 s on these bytes -- worth recording, because T-1344 owns both
"run the declared family" and "record its failing set as a baseline", and a
one-shot run here cannot even complete. It was therefore run module by module
(139 modules), each bounded at 150 s, and every failure was compared BY TEST
IDENTITY against a pristine `git archive HEAD` export of the same revision.

    chunk A      671 tests   21 failures + 1 error
    chunk B1     294 tests    6 failures
    chunk C       35 modules  34 clean,  1 red
    chunk D       34 modules  31 clean,  3 red (one is a timeout, see below)
    13 remaining modules individual: 4 clean, 9 not completed in this window

| failing module | worktree | pristine HEAD | verdict |
|---|---|---|---|
| test_recovered_attribution | 20 F + 1 E | 20 F + 1 E | inherited (same identities) |
| test_install_drift | 1 F | 1 F | inherited |
| test_explicit_claim | 5 F | 5 F | inherited (T-1346 recorded) |
| test_concurrency_independence | 1 F | 1 F | inherited (T-1347 recorded) |
| test_intent_audit_fixes | 4 F | 4 F | inherited (T-1346 recorded) |
| test_audit_2026_08_28_all3 | 1 F | 1 F | inherited |
| test_inject_digest | 1 F | 1 F | inherited |
| test_conformance_lineage | timeout (>150 s) | timeout (>150 s) | inherited |

    PATCH_OWNED  = 0   (every observed failure reproduces byte-identically at
                        HEAD, by test identity, not by count)
    UNKNOWN      = 0   for the 126 modules that were run
    NOT RUN      = 13  modules: a live-host module leaves a child process
                        holding the pipe, which hangs the invoking shell even
                        under `timeout`. Those modules are UNVERIFIED here and
                        are named rather than implied: test_ledger_gap,
                        test_log_stamp_guard, test_narrative_authority,
                        test_opencode_bound_launch_smoke,
                        test_opencode_live_session,
                        test_project_root_session_binding,
                        test_reconcile_legacy_output_field,
                        test_recovery_noop_targets, test_settled_projection,
                        test_t1304_r004_transition,
                        test_unknown_tool_fail_closed,
                        test_validator_layout_parity, test_xpatch.

                        (test_reconcile_legacy_output_field,
                        test_recovery_noop_targets, test_settled_projection and
                        test_ledger_gap DO pass in the adjacent-family runs
                        above; the rest have no measurement from this session.)

Two validate.py FAILs were fixed by staging the two files this ticket adds
(the runtime manifest refuses a manifest entry git does not track); the
validator then reports: **Validation complete. Agent is conformant.**

---

# Closure of the 13-module gap -- 18.09.26, current bytes @5d79ae78+

The prior pass could not measure 13 modules because a live-host child held
the output pipe and hung the invoking shell even under a timeout. That was a
transport artifact, not a property of the modules: every module now runs with
its stdout/stderr redirected to its own FILE under
`modules/` (no pipe to hold), a per-module wait bound, and a kill that cannot
strand the driver (`modules/_driver.py` verbatim). Per-module transcripts and
`modules/summary.json` live beside this file.

    test_ledger_gap                     PASS   0.1 s
    test_log_stamp_guard                PASS   0.1 s
    test_narrative_authority            PASS   0.1 s
    test_opencode_bound_launch_smoke    PASS  35.7 s
    test_opencode_live_session          PASS   0.1 s
    test_project_root_session_binding   PASS   1.9 s
    test_reconcile_legacy_output_field  PASS   0.3 s
    test_recovery_noop_targets          PASS   0.6 s
    test_settled_projection             PASS  31.1 s
    test_t1304_r004_transition          PASS   3.3 s
    test_unknown_tool_fail_closed       PASS   2.1 s
    test_validator_layout_parity        PASS   9.3 s
    test_xpatch                         PASS   0.9 s

Zero failures, zero timeouts. Nothing to attribute against a pristine HEAD
run: with all 13 green, the family totals close as

    PATCH_OWNED  = 0
    UNKNOWN      = 0
    UNMEASURED   = 0

over the declared `python -m unittest discover -s tools -p "test_*.py"`
family (126 modules measured in the prior pass with every failure reproduced
byte-identically at pristine HEAD by test identity; 13 modules above). The
eight inherited reds and their owning tickets (T-1346, T-1347, T-1344 for the
declared-family timeout) are unchanged and not this ticket's to fix.

## Dirty-tree ownership at closure

The tree carries several parallel actors' uncommitted bytes. Attributed by
reading every diff, not by guessing:

    T-1382 (this commit)          tools/saipen.py (recover --resolve-duplicate-id
                                  wiring), tools/saipen_engine/board.py
                                  (board_record_digest, duplicate_records),
                                  tools/saipen_engine/reconcile.py (duplicate-id
                                  decision carrier, spent-id allocator honours,
                                  RESIDUAL_DEFECTS), tools/saipen_engine/
                                  fast_check.py (docstring: FIVE malformed LOG
                                  lines, the measured fixture), the three test
                                  files and this evidence directory.
                                  board.py/reconcile.py are the 543 insertions
                                  E-7050 measured as written by a concurrent
                                  opencode runtime: that runtime was executing
                                  THIS ticket's BUILD. The functions are the
                                  Specimen B carrier this PROOF documents and
                                  the regression families exercise; ownership
                                  resolves to T-1382 on content, not on which
                                  runtime typed them.
    excluded, foreign             tools/saipen_engine/entry.py (T-1388's three
                                  root= passes -- its corrective commit owns
                                  them), tools/saipen_engine/admission.py +
                                  extensions/adapters/opencode/saipen-guard.js
                                  (T-1385's PROTECTED_CANONICAL_NAMESPACE route),
                                  bootstrap/inject.ps1, bootstrap/inject.sh,
                                  tools/saipen_engine/runtime_bootstrap.py
                                  (T-1389's unowned foreign injector delta),
                                  CHANGELOG*.md (E-7041 CLEAN compaction),
                                  .saipen/ protocol state, SubSaipen surfaces
                                  and the fresh RAPORT-* evidence directories
                                  (T-1394 triage input, untouched here).

    tools.test_t1326_board_compaction (the frozen-seat claim-cap control this
    corridor added) passes at pristine HEAD engine bytes with only the test
    file copied in: it PINS existing behaviour, it does not depend on this
    ticket's engine delta.

## Final gates on the closing bytes

    tools.test_recovery_reachability + tools.test_defect_delta_controls
                                                  Ran 96   OK
    tools.test_t1326_board_compaction             Ran 94   OK
    13 previously-unmeasured modules              Ran 13 modules, all OK
    adjacent recovery/routing/binding/guard/
      board/journal/validator batch (43 modules)  recorded in LOG; every
                                                  failure in it reproduces in
                                                  the inherited baseline above
    ruff, T-1382-owned files                      All checks passed
    tools/validate.py                             conformant, 0 FAIL
                                                  (22 warnings, each owned by
                                                  another ticket's slug)
