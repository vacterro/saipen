SAIPEN

MULTI-MILESTONE AUTONOMOUS CONTINUATION — RECOVER T-1446, COMPLETE L3 AUTONOMY PRIMITIVES, PROVE SUPERVISOR TURNOVER, THEN ADVANCE TO SOAK GATES

THIS IS CONTINUATION GUIDANCE FOR THE EXISTING T-1446 / SRC-100 AUTONOMY MISSION.

Do NOT create:
- another autonomy umbrella;
- another `cc all` goal ticket;
- another duplicate Source;
- another generic continuation ticket;
- another replacement roadmap.

Do NOT use `cc all` as a substitute for current-work continuation.

Preferred first action:

    saipen continue --json

Live canonical STATE / BOARD / LOG at execution time always wins.

======================================================================
0. KNOWN SNAPSHOT TO RECOVER FROM
======================================================================

Last archived canonical snapshot:

    STATE:
        phase: DONE
        task: none
        next_action: PHASE SCOUT T-1446
        last_event: E-7925

Known BOARD:

    T-1446 P1 TODO
        SRC-100
        needs:
            T-1447 DONE
            T-1448 DONE

    T-1449 P1 BLOCKED
        cc all
        declared unittest family exceeded bounded 600-second window
        no PASS claimed

    T-1450 P1 BLOCKED
        cc all
        duplicate semantic goal ingress of T-1449
        no new scope
        no rerun justified

    T-1428 P1 BLOCKED on T-1446
        resume_phase BUILD

Completed and preserved:

    T-1447 DONE
        audit_checks child-process carrier hermeticity

    T-1448 DONE
        watchdog heartbeat
        mutation lease generation
        stale/expired detection
        old-generation fencing

Do NOT reopen T-1447/T-1448 without a measured regression.

If live state has advanced beyond this snapshot:

    preserve all newer canonical work
    recover from current state
    do NOT rewind to E-7925

======================================================================
1. FIRST RECOVERY TARGET — RESTORE T-1446 AS THE REAL MISSION
======================================================================

Run:

    saipen continue --json

Expected semantic:

    choose/resume the existing eligible T-1446

NOT:

    create another goal
    retry T-1449
    retry T-1450
    create T-1451 for "continue"

If scheduler instead reports DONE/idle while T-1446 remains eligible:

    this is a WORKABILITY defect

Reuse:

    T-1302

Do not create a duplicate scheduler owner.

If scheduler selects T-1449/T-1450:

    do not rerun their unchanged expensive family

Their evidence already exists.

Required recovery result:

    T-1446 becomes active/resumable

    T-1449 remains preserved as bounded INCOMPLETE evidence

    T-1450 remains preserved as duplicate-ingress evidence

    neither one globally blocks T-1446

======================================================================
2. DO NOT MISDIAGNOSE UTC CLAIM TIMES
======================================================================

A recent investigation almost produced a false ownership bug.

Observed example:

    claim_time:
        2026-09-21T23:14:36Z

Local Estonia/Tallinn equivalent:

        2026-09-22T02:14:36+03:00

With:

    LIVENESS_WINDOW = 15 minutes

the claim remains legitimately live until:

        2026-09-21T23:29:36Z
        =
        2026-09-22T02:29:36+03:00

Therefore:

    WAIT_FOREIGN_OWNER

during that interval is correct.

Do NOT patch:

    claim_status
    session_locked_out
    FOREIGN_LIVE
    FOREIGN_STALE

based on manually subtracting local clock text from a UTC `Z` timestamp.

All liveness tests and diagnostics must use parsed timezone-aware instants.

Never compare timestamp strings or naive datetimes.

----------------------------------------------------------------------
OWNERSHIP DIAGNOSTIC REQUIREMENT
----------------------------------------------------------------------

Improve diagnostic observability ONLY if current architecture has a legal owner
for it and no equivalent surface already exists.

Useful structured output should expose:

    claim_status
    claim_owner
    claim_time_utc
    now_utc
    claim_age_seconds
    liveness_window_seconds
    expires_at_utc
    expires_in_seconds
    claim_session
    current_host_session
    session_binding_status
    exact reason

Example:

    status: FOREIGN_LIVE
    reason: CLAIM_WITHIN_LIVENESS_WINDOW
    claim_age_seconds: 384
    liveness_window_seconds: 900
    expires_in_seconds: 516

This is diagnostic evidence, not a new authority.

Do NOT block T-1446 merely to polish diagnostics.

======================================================================
3. REAL OWNERSHIP RED CONTROL — ONLY AFTER EXPIRY
======================================================================

The timezone example is NOT a valid RED.

If ownership logic is touched, use deterministic injected `now` values.

Required test:

    claim_time = T0
    liveness_window = 15m

At:

    T0 + 14m59s
        -> FOREIGN_LIVE

At:

    T0 + 15m01s
        -> FOREIGN_STALE

Then prove adoption behavior according to policy.

Also test:

    actor == owner
    actor != owner
    matching claim_session
    foreign claim_session
    missing session
    corrupt timestamp
    future timestamp / clock skew

A future/clock-skewed stamp must receive an explicit safe classification.

Do NOT rely on sleeping 15 real minutes in unit tests.

======================================================================
4. KEEP T-1442 DISTINCT
======================================================================

T-1442 remains an existing measured issue:

    dependency-resume ownership classification
    can interact with SAIPEN_HOST_SESSION

Do not conflate it with the timezone misunderstanding.

The UTC example:

    NOT T-1442 proof

T-1442 should only be changed if its own reproduction remains valid.

Its key invariant:

    dependency completion itself must not synthesize a new live claim merely
    from historical owner/session metadata

Historical:

    owner
    claim_session
    claim_time

are not independently sufficient proof of current process liveness.

Watchdog/runtime evidence may contribute to liveness according to canonical
policy.

If T-1442 is required for T-1446 worker turnover:

    repair T-1442 through its existing owner
    verify
    close
    automatically return to T-1446

======================================================================
5. T-1449/T-1450 INCIDENT — MAKE DUPLICATE INGRESS IDEMPOTENT
======================================================================

Current behavior detected duplicate semantic goal only AFTER T-1450 existed.

That is insufficient for long-running autonomy.

Target behavior:

    same explicit goal authority
    same semantic scope
    existing nonterminal/blocked goal already represents it

=> no new Work

Return a canonical result such as:

    ALREADY_CAPTURED

or reuse the existing Work identity according to current protocol grammar.

Do NOT invent string-similarity deduplication.

Prefer deterministic identity from:

    normalized command/goal contract
    Source authority
    project identity
    target scope
    relevant parameters

Tests:

A.
    identical goal while original active
        -> no duplicate

B.
    identical goal after original ticket-scope BLOCKED
        -> no duplicate

C.
    identical goal after bounded timeout
        -> no duplicate expensive rerun

D.
    same words but materially different target/scope
        -> new Work allowed

E.
    same goal with new explicit evidence that changes acceptance
        -> legal continuation/update according to protocol

F.
    retry after original terminal DONE
        -> policy-defined behavior
        -> must not silently resurrect historical Work

Use the T-1449/T-1450 incident as regression evidence.

======================================================================
6. COLD RECOVERY PACKAGE — NEXT PRIMARY T-1446 SLICE
======================================================================

After T-1446 is active again, continue the slice selected before the cc-all
incident:

    COLD RECOVERY PACKAGE

Do NOT make another canonical authority file.

Produce a DERIVED recovery carrier from canonical state/evidence.

Core principle:

    AGENT IS DISPOSABLE
    STATE IS NOT

A fresh worker with zero chat context must learn enough to act safely.

Required bounded recovery fields:

    project_id
    canonical_root
    active_or_resumable_work
    phase
    last_event
    parent/dependency context
    current owner
    mutation lease generation
    liveness classification
    last verified bounded slice
    last durable checkpoint
    evidence references
    source/tree identity
    dirty identity where relevant
    current blocker
    blocker scope
    deferred gates
    due operator actions
    classified current reds
    classified unrelated reds
    do_not_repeat
    exact_next_action

No full LOG duplication.

No chat transcript.

No prose summary as authority.

Recovery package must be regenerable.

======================================================================
7. COLD RECOVERY MUST PASS THE CURRENT REAL INCIDENT
======================================================================

A cold worker sees:

    STATE may say DONE / task none

BOARD contains:

    T-1446 eligible
    T-1449 BLOCKED
    T-1450 BLOCKED
    T-1428 blocked_on T-1446

Correct interpretation:

    current project is NOT globally DONE

    T-1446 is resumable/eligible

    T-1449/T-1450 are local blocked side branches

    T-1428 remains downstream

Cold recovery output must lead to an executable action equivalent to:

    saipen continue --json

and eventually T-1446.

Forbidden:

    no work
    project complete
    retry T-1449
    create another goal
    raw BOARD repair

This is a real field fixture for L3 autonomy.

======================================================================
8. COLD WORKER ACCEPTANCE
======================================================================

Create a controlled test:

Worker A:

    receives Work
    performs bounded mutation
    verifies
    checkpoints
    terminates

Worker B:

    starts with:
        repository only
        no chat
        no model memory
        no previous scratchpad

Worker B must:

    orient
    recover active/resumable Work
    identify completed slice
    avoid repeating it
    obtain exact next action
    continue

Measure:

    files read
    bytes read
    wall time
    commands before useful action

Target:

    useful continuation <= 5 minutes

Do not call a second function in the same process "cold worker".

Use a genuinely fresh process/session boundary where the available host permits.

If actual worker spawning is unavailable:

    distinguish deterministic recovery proof
    from real worker-turnover proof

======================================================================
9. PROGRESS INVARIANT — BUILD ON EXISTING autonomy.py
======================================================================

Inspect:

    tools/saipen_engine/autonomy.py
    ProgressTracker

Do not create a competing loop detector.

Current/legacy mechanics may include:

    repeated-observation threshold
    oscillation detection
    max_iterations

SRC-100 requires a stronger semantic rule.

Target:

    5 semantically equivalent no-progress cycles
        -> NO_PROGRESS_LOOP

Do NOT implement this as:

    same string five times

Progress fingerprint should use relevant semantic identities:

    Work
    phase
    blocker
    blocker scope
    exact next action
    source/tree identity
    authority state
    failure identity set
    evidence identity
    dependency terminality

Timestamp is not progress.

Heartbeat is not progress.

More tokens written to logs is not progress.

======================================================================
10. NO-PROGRESS ACCEPTANCE
======================================================================

Required cases:

A.
    same Work
    same phase
    same blocker
    same next action
    same evidence
    5 cycles

        => NO_PROGRESS_LOOP

B.
    same command after source bytes changed

        => may be legitimate retry

C.
    same command after authority changed

        => legitimate retry

D.
    same command after dependency became terminal

        => legitimate retry

E.
    only timestamps changed

        => still no progress

F.
    worker still executing one known long-running command and heartbeat is
    healthy

        => RUNNING
        not loop

G.
    T-1449 already has unchanged 600-second timeout evidence

    another request to run the same family with no changed hypothesis

        => DO_NOT_REPEAT / NO_NEW_EVIDENCE

H.
    looped Work + another eligible Work

        => park/classify looped Work
        => continue other eligible Work

No loop escape may weaken a safety invariant.

======================================================================
11. EXPENSIVE TEST BUDGET POLICY
======================================================================

The T-1449 incident exposed another autonomy requirement.

A 600-second family that produces no verdict must not automatically be rerun.

Every expensive rerun requires at least one:

    relevant source bytes changed
    harness changed
    environment hypothesis changed
    timeout policy intentionally changed
    previous run corrupt/incomplete for a known recoverable reason

Otherwise:

    NO_NEW_EVIDENCE
    DO_NOT_REPEAT

Recovery carrier must surface this.

Supervisor must respect it.

Do not allow a 24H autonomous run to spend 20 hours repeating the same
20-minute test.

======================================================================
12. WORKABILITY — REUSE T-1302
======================================================================

Now integrate the existing T-1302 owner.

Required scheduler classes:

    WORKABLE
    BLOCKED_TICKET
    BLOCKED_GOAL
    DEFERRED_OPERATOR
    DUE_OPERATOR_ACTION
    RELEASE_GATED
    USER_INTERRUPT
    GLOBAL_STOP

Critical invariant:

    BLOCKED_TICKET != GLOBAL_STOP

Real acceptance fixture:

    T-1449 BLOCKED
    T-1450 BLOCKED
    T-1446 eligible

Expected:

    choose T-1446

If T-1302 cannot do this:

    execute T-1302 as a bounded dependency child
    verify
    close
    return to T-1446

Do not let T-1302 swallow T-1446.

======================================================================
13. USER INTENT VS CONTINUATION
======================================================================

Explicit user intent must remain durable.

But broad shorthand like:

    cc all

must not unnecessarily replace an already active compatible explicit mission.

Define deterministic precedence.

Possible categories:

    NEW_TARGET
    CONTINUE_CURRENT
    EXPAND_CURRENT
    DUPLICATE_CURRENT
    INTERRUPT_CURRENT

Do not infer purely from natural-language similarity.

The protocol needs machine-level criteria.

Acceptance:

    "continue"
        -> continue current

    same cc-all twice
        -> duplicate/idempotent

    explicit materially different new target
        -> user interrupt semantics

    explicit expansion of active source
        -> preserve active authority and append scope according to protocol

No silent loss of existing mission.

======================================================================
14. DUE-TIME — REUSE T-1429
======================================================================

T-1429 owns machine-readable deferred gates.

Implement/reuse it before 24H operation.

Required:

    due_at / retry_not_before / equivalent one canonical field

Before due:

    DEFERRED_OPERATOR

After due:

    DUE_OPERATOR_ACTION

A timestamp embedded only in prose:

    must not activate anything

Unrelated Work continues.

FreeBuff T-1426 may remain the first live fixture.

Do NOT consume FreeBuff quota automatically.

Do NOT perform its human GUI acceptance automatically.

======================================================================
15. WATCHDOG INTEGRATION — PRESERVE T-1448
======================================================================

T-1448 provides the primitive.

Now integrate it with recovery/workability.

Worker states should support:

    HEALTHY
    SUSPECT
    EXPIRED
    TERMINAL
    UNKNOWN

Mutation policy:

    UNKNOWN
        -> no blind takeover

When worker becomes EXPIRED:

    fence its generation
    preserve durable checkpoint
    release/recover lease safely
    replacement claims a NEW generation

If old worker later returns:

    mutation rejected because generation is fenced

Do not use owner string equality as fencing.

======================================================================
16. CLOCK MODEL FOR WATCHDOG
======================================================================

All watchdog/lease timing must use timezone-aware UTC instants or monotonic
durations where appropriate.

Persisted inter-process timestamps:

    UTC

Elapsed-process timing:

    monotonic clock where possible

Never:

    subtract local wall-clock string from UTC ISO text

Tests must inject/freeze time.

Required clock-skew cases:

    exactly before expiry
    exactly after expiry
    timestamp in future
    local DST/timezone irrelevant
    system wall-clock jumps backwards
    process monotonic duration unaffected where applicable

Do not make the autonomy supervisor depend on Estonia specifically.

======================================================================
17. SUPERVISOR — ONLY AFTER RECOVERY/PROGRESS/WORKABILITY
======================================================================

Do not build a daemon first.

Prerequisites:

    cold recovery green
    duplicate ingress controlled
    no-progress semantics green
    T-1302 workability green
    watchdog fencing green
    due-time semantics available

Then create/reuse ONE bounded supervisor owner.

Supervisor responsibilities:

    observe project
    calculate eligibility
    acquire mutation lease
    launch/adopt one worker
    monitor heartbeat
    observe checkpoint
    detect worker death
    fence stale generation
    recover exact next Work
    launch replacement
    handle deferred gates
    avoid no-progress reruns
    expose status

Supervisor does NOT own product truth.

It orchestrates canonical Work.

======================================================================
18. RUNTIME-LOCAL SUPERVISOR STATE
======================================================================

Runtime state may include:

    autonomy_run_id
    supervisor_generation
    current_worker_generation
    lease_generation
    current Work
    current slice
    heartbeat time
    last checkpoint
    progress fingerprint
    no_progress_count
    retry state
    next wake time
    stop reason

This state is:

    runtime-local
    derived/reconstructable

It is NOT:

    replacement STATE.md
    replacement BOARD.md
    source/release evidence by itself

Durable semantic transitions still flow through SAIPEN protocol.

======================================================================
19. CONTROLLED WORKER TURNOVER
======================================================================

Before chaos/soak, prove sequential turnover.

Minimum:

    Worker A
    -> checkpoint
    -> terminate

    Worker B cold
    -> recover
    -> claim new generation
    -> continue
    -> checkpoint
    -> terminate

    Worker C cold
    -> recover
    -> continue

Required:

    operator messages between turnovers = 0

    duplicate semantic mutations = 0

    completed slices repeated = 0

    wrong Work selected = 0

    old worker accepted after fencing = 0

    exact next action recovered each time

Minimum:

    3 worker generations

If the execution host cannot launch independent workers:

    report actual missing capability

Do not simulate a subprocessless function call and label it real turnover.

======================================================================
20. SUPERVISOR RESTART
======================================================================

Separate test:

    worker remains or dies
    supervisor process disappears
    supervisor restarts from zero RAM state

It must reconstruct:

    run identity where recoverable
    current lease
    worker health
    Work
    next legal action

No assumption that supervisor remembers anything.

If ambiguity exists:

    fail closed for mutation
    investigate/reconcile from durable journal

No double worker launch.

======================================================================
21. PROVIDER / MODEL AVAILABILITY
======================================================================

Use generic failure classes.

At minimum:

    QUOTA_EXHAUSTED
    RATE_LIMITED
    AUTH_FAILED
    PROVIDER_UNAVAILABLE
    MODEL_UNAVAILABLE
    NETWORK_UNAVAILABLE
    HOST_RUNTIME_FAILURE
    WORKER_CRASH
    UNKNOWN

For transient availability:

    preserve Work
    preserve checkpoint
    release/fence appropriate runtime generation
    retry later
    or use authorized configured fallback

Fallback must never:

    invent credentials
    spend unapproved funds
    consume reserved external quota
    silently violate model policy

Provider failure != protocol failure.

======================================================================
22. AUTONOMOUS CHECKPOINT CADENCE
======================================================================

Ticket transitions are insufficient for day-scale operation.

While meaningful active work continues:

    create durable checkpoint at least every 60 minutes

Checkpoint records:

    Work
    phase
    bounded slice
    last verified result
    tree identity
    evidence identity
    blocker/deferred status
    exact next action
    progress fingerprint
    no-progress count

Do not checkpoint every shell command.

If the last hour produced no semantic progress:

    record NO_PROGRESS honestly

not fake an achievement.

======================================================================
23. OBSERVABILITY SURFACE
======================================================================

Provide/reuse one read-only surface exposing:

    autonomy run id
    project
    supervisor state
    worker generation
    lease generation
    heartbeat age
    current Work
    phase
    slice
    elapsed run time
    elapsed since semantic progress
    last checkpoint
    blocker
    deferred gates
    due actions
    provider retry
    no-progress count
    exact next action
    stop reason

Status must work when:

    no Work is currently active

Routine observation must not require manually opening raw BOARD/STATE/LOG.

Raw canonical files remain debugging/authority surfaces.

======================================================================
24. CHAOS GATE — ACCELERATED
======================================================================

Before any one-hour soak, run a bounded chaos polygon on disposable projects.

Include:

    duplicate continuation/goal ingress
    one blocked + one eligible Work
    deferred human gate
    healthy worker
    dead worker
    frozen heartbeat
    stale lease
    old worker returns
    worker dies before checkpoint
    worker dies after checkpoint
    supervisor restart
    cold worker replacement
    repeated unchanged expensive test
    NO_PROGRESS_LOOP
    provider unavailable simulation
    user interrupt
    all Work genuinely blocked

Required:

    no stolen lease
    no double mutator
    no lost Work
    no lost user Source
    no fabricated PASS
    no raw canonical edits
    no false project DONE
    no false GLOBAL_STOP

Use T-1449/T-1450 as a modeled regression shape.

======================================================================
25. ONE-HOUR SOAK
======================================================================

Only after chaos gate is green.

Run a real local one-hour autonomy session.

Require during the hour:

    multiple bounded slices
    at least 3 worker generations if host supports it
    at least 1 deliberate worker death
    at least 1 deferred/blocked Work
    at least 1 unrelated Work selected after a block
    periodic checkpoint
    status observation

Measure:

    manual_continue_count
    worker_generations
    crash_recoveries
    maximum_recovery_latency
    duplicate_semantic_mutations
    stolen_leases
    false_global_stops
    fabricated_passes
    unknown_terminal_failures
    checkpoints
    no_progress_detections
    expensive_reruns_prevented

Acceptance:

    manual_continue_count = 0
    duplicate_semantic_mutations = 0
    stolen_leases = 0
    false_global_stops = 0
    fabricated_passes = 0
    unknown_terminal_failures = 0
    raw canonical manual edits = 0

Target:

    worker recovery <= 5 minutes
    cold continuation <= 5 minutes

If host cannot launch replacement workers:

    1H gate cannot claim full PASS
    classify exact environmental boundary

======================================================================
26. 24H FIELD GATE
======================================================================

Only after:

    deterministic tests green
    chaos gate green
    1H soak credible

Target:

    24 real hours unattended

Do NOT fake elapsed wall time.

Do NOT require one LLM session to survive 24h.

The field run must survive:

    worker session turnover
    context loss
    transient worker failure
    supervisor restart where testable

Required metrics:

    manual_continue_count = 0

    duplicate_semantic_mutations = 0

    stolen_live_leases = 0

    fabricated_pass = 0

    unknown_terminal_failure = 0

    raw canonical manual edits = 0

    false project-wide stops from one deferred ticket = 0

    progress checkpoint gap while active <= 60 min

    worker/cold recovery <= 5 min target

Human-only gate:

    surfaced
    parked
    unrelated Work continues

======================================================================
27. DO NOT HOLD MUTATION SEAT FOR A CLOCK
======================================================================

If implementation is complete and only the 24-hour field timer remains:

    a wall-clock wait must NOT own the only mutation seat

Use canonical deferred/field-acceptance representation.

Expected:

    24H acceptance run observed separately
    T-1446 field gate deferred/running truthfully
    unrelated T-1428 work may resume when mutation safety permits

If the actual field worker is mutating SAIPEN:

    it owns the lease

But idle waiting for elapsed time is not mutation authority.

======================================================================
28. T-1446 TERMINAL CONDITIONS
======================================================================

Do NOT close T-1446 just because watchdog exists.

Implementation-side acceptance requires:

    duplicate ingress idempotence
    cold recovery
    cold worker continuation
    semantic progress/no-loop
    workability scheduler
    due-time/deferred semantics
    liveness/fencing integration
    supervisor
    supervisor restart behavior
    observable status
    chaos polygon
    one-hour soak or truthful host boundary

For the real 24H field gate:

    PASS

or:

    one exact truthfully deferred/external runtime boundary

No "basically passed".

======================================================================
29. RESUME T-1428
======================================================================

When T-1446 becomes terminal OR only a non-seat-holding field gate remains:

resume:

    T-1428 / SRC-083

Do not make a new roadmap.

Known preserved T-1428 context:

    T-1346 DONE
    T-1345 DONE

    T-1344 measured declared core family earlier:
        3206 tests
        150 failures
        3 errors
        17 skipped
        rc 1
        approx 1726s

That old broad result is NOT T-1446 work.

Do not repair its 153 historical manifestations under autonomy unless an exact
one blocks autonomy infrastructure.

After T-1446:

    return T-1428 to T-1344 classification/closure corridor

then continue existing roadmap.

======================================================================
30. T-1449 / T-1450 DISPOSITION
======================================================================

Do not delete history.

T-1449 proves:

    bounded full-family timeout without verdict

T-1450 proves:

    duplicate goal created before duplicate was rejected

Keep both as evidence until canonical lifecycle has a legal terminal
classification.

Possible desired terminal semantics must be discovered from current protocol.

Do not raw-edit them to DONE.

Do not rerun unchanged T-1449.

Do not create T-1451 just to close T-1450.

======================================================================
31. EXPENSIVE VALIDATION POLICY
======================================================================

Use layered verification.

For each bounded change:

    RED reproduction
    smallest focused GREEN
    necessary neighbors

Only run broad expensive families at meaningful convergence boundaries.

Before any >5 minute run ask mechanically:

    what changed?
    what hypothesis does this test?
    what new evidence can it produce?

If answers are identical to previous run:

    do not run

This rule should eventually become machine-enforced by progress/recovery
metadata where practical.

======================================================================
32. LONG-RUN CONTRACT
======================================================================

This handoff is designed for HOURS of sequential autonomous work.

One bounded root/child at a time.

After each:

    reproduce
    identify existing owner
    implement bounded fix
    RED/GREEN verify
    review
    checkpoint
    terminalize/block truthfully
    return to parent
    select next legal slice
    continue automatically

Do not ask:

    continue?

Do not issue:

    cc all

as generic continuation.

Use canonical current-work continuation.

Do not stop because:

    one ticket blocks
    one human gate defers
    one test times out
    one provider is unavailable
    one secondary P2/P3 exists
    one field clock is running
    context is approaching its limit

Before context exhaustion:

    durable checkpoint
    fresh recovery carrier
    exact next action
    exact DO_NOT_REPEAT list
    source/tree identity
    active run identity
    blocker classification

======================================================================
33. HARD STOP CONDITIONS
======================================================================

Stop only when:

    security/integrity P0 makes further mutation unsafe

    irreversible destructive action lacks authority

    all eligible Work is truly externally blocked

    a genuine human choice is required and no unrelated Work exists

    evidence proves the autonomy architecture unsafe

    real worker/supervisor runtime capability required for the next field gate
    is absent

A live foreign claim inside its legitimate liveness window is:

    WAIT

not:

    ownership bug

But while waiting on that one seat:

    continue unrelated legally eligible work where possible.

======================================================================
34. PUBLICATION BOUNDARY
======================================================================

No:

    push
    tag
    GitHub Release
    package publication
    FreeBuff quota consumption
    unapproved paid provider usage

Local reversible implementation/test work only under current authority.

Autonomy acceptance != release/publication authority.

======================================================================
35. SESSION-END REPORT
======================================================================

Do not return after merely fixing duplicate ingress.

Do not return after merely implementing cold recovery.

Continue while legal work and capacity remain.

At genuine session end report:

STATUS

LIVE CANONICAL OWNER

T-1446 RECOVERY

T-1449 DISPOSITION

T-1450 DISPOSITION

DUPLICATE INGRESS STATUS

UTC / CLAIM-LIVENESS DIAGNOSTIC STATUS

T-1442 STATUS

COLD RECOVERY PACKAGE

COLD WORKER ACCEPTANCE

PROGRESS / NO_PROGRESS_LOOP

EXPENSIVE RERUN PREVENTION

T-1302 WORKABILITY

T-1429 DUE-TIME

T-1448 WATCHDOG INTEGRATION

SUPERVISOR STATUS

SUPERVISOR RESTART STATUS

WORKER GENERATIONS TESTED

PROVIDER FAILURE HANDLING

OBSERVABILITY

CHAOS GATE

1H SOAK

24H FIELD GATE

MANUAL CONTINUE COUNT

DUPLICATE SEMANTIC MUTATION COUNT

STOLEN LEASE COUNT

FALSE GLOBAL STOP COUNT

UNKNOWN TERMINAL FAILURES

MAX RECOVERY LATENCY

T-1446 CLOSURE STATUS

T-1428 RESUME STATUS

PUBLICATION STATUS

EXACT NEXT ACTION

COLD-AGENT RECOVERY

The exact next action must be executable.

Do NOT end with:

    continue?

Do NOT end with:

    cc all

Do NOT rerun unchanged T-1449.

Do NOT report a claim-liveness defect based on local-vs-UTC arithmetic.