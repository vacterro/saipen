SAIPEN
MULTI-MILESTONE AUTONOMOUS CONTINUATION — RECONCILE THE CURRENT T-1446 DELTA, SHIP THE RUNTIME LOCALLY, THEN COMPLETE THE REAL UNATTENDED SUPERVISOR / CHAOS / SOAK BOUNDARY
THIS HANDOFF SUPERSEDES EARLIER T-1446 CONTINUATION HANDOFFS.
Do not create another autonomy umbrella.
Do not create another generic continuation ticket.
Do not create another Source for SRC-100.
Do not use `cc all`.
Do not raw-edit STATE.md, BOARD.md, or LOG.md.
Do not reset, clean, stash, discard, or overwrite the existing dirty tree.
Do not rerun an expensive family merely because an older run timed out.
Do not push, tag, publish a release, consume paid provider quota, or spend external quota.
Live canonical STATE / BOARD / LOG at execution time always wins over this snapshot.
======================================================================
0. VERIFIED SNAPSHOT
Archive snapshot inspected:

```
HEAD:
    d97abdc097db432bafe2316b1e3577e44cd9cc4c

VERSION:
    8.0.1

STATE:
    phase: BUILD
    task: T-1446
    next_action: PHASE BUILD T-1446
    blocker: none
    last_event: E-7975
    execution_intent: goal
    agent: astra

BOARD:
    T-1446 P1 DOING
    T-1457 P0 TODO
    T-1456 P2 TODO
    T-1455 P2 TODO
    T-1454 P1 TODO
    T-1453 P1 TODO
    T-1452 P1 TODO
    T-1451 P2 TODO

```

Completed prerequisites:

```
T-1447 DONE
T-1448 DONE
T-1302 DONE

```

Do not reopen those three without a newly measured regression.
Current status reports:

```
active_work:
    T-1446

top_workable_ticket:
    T-1457

```

This is important.
T-1457 is still TODO because lifecycle reconciliation has not caught up with its implementation evidence. Do not mistake that for permission to implement the same fix again.
======================================================================

1. NEW WORK ALREADY PRESENT IN THE CURRENT TREE
======================================================================

The following implementation work already exists and has current evidence.
T-1457

```
ingress_payload now stops at the quoted request boundary rather than
recording trailing shell transport bytes as the owed payload.

Legacy obligations can be discharged by the actual request.

status exposes the obligation instead of requiring a mutating ingress probe.

E-7974:
    test_t1457 PASS 18
    guard + entry PASS 185
    red controls PASS by failing the pre-fix shape

E-7975:
    test_t1457 PASS 20
    guard + autonomy families PASS 262

```

T-1456

```
hush is now treated as an execution-policy modifier rather than an unknown
execution verb.

hush status classifies DIAGNOSTIC.

E-7971:
    vocabulary parity PASS 20
    3 red controls detect pre-fix behavior

```

T-1455

```
SOURCE_* coverage refusals now route through one structured owner.

E-7961:
    source_refusal_routing PASS 6
    source families PASS 103

```

T-1454

```
distribution diagnostics now name DIRTY_SOURCE, the affected surface paths,
and the exact clearing command.

E-7962:
    T-1454 focused PASS 9
    distribution family PASS 34

HOWEVER:
    T-1454 IS NOT YET COMPLETE.

Its acceptance also requires:
    runtime manifest contains no runtime file absent from Git
    repaired protocol bytes can actually reach installed homes from a
    committed source identity

```

T-1453

```
headerless `source capture --file` bodies now receive a canonical request
clause through the request-kind owner.

E-7958:
    T-1453 + source families PASS 99

E-7963:
    SRC-039 / SRC-042 / SRC-043 residue discharged canonically

```

T-1452

```
audit manifest contract now excludes transient nested runtime material while
retaining durable material.

E-7959:
    audit manifest family PASS 66

```

T-1429

```
deferred operator-gate eligibility now has a single canonical classifier.

E-7951:
    focused deferred-due + cold-recovery + watchdog PASS 55

E-7952:
    routing / continue / refusal / orchestration neighbors PASS 245

E-7957:
    cold_recovery PASS 28
    false DUE count reduced to zero
    one real operator gate remains: T-1317

```

T-1446

```
supervisor decider exists.

E-7965:
    supervisor PASS 27
    5 pre-fix red controls

E-7968:
    three real OS worker generations
    deliberate os._exit crashes
    fence + replace
    zero-RAM supervisor reconstruction
    worker_turnover PASS 9

E-7969:
    autonomy surface carries durable checkpoint, last progress,
    stop reason and canonical next command
    supervisor + turnover PASS 40

E-7967:
    AMBIGUOUS_AUTHORITY and LIVE_LEASE_PRESENT registered
    313 tests PASS across 17 families

```

Independent archive audit performed after E-7975:

```
176 tests PASS

```

Covering:

```
tools.test_t1457_ingress_obligation
tools.test_guard_events
tools.test_supervisor
tools.test_worker_turnover
tools.test_t1454_distribution_blocker
tools.test_t1453_ingress_clause
tools.test_t1452_manifest_authority
tools.test_source_refusal_routing
tools.test_vocabulary_parity

```

Do not re-implement these fixes unless a current RED proves regression.
======================================================================
2. FIRST MILESTONE — RECONCILE AND TERMINALIZE IMPLEMENTED WORK
Start with:

```
saipen continue --json

```

Recover current live truth first.
Then reconcile the currently implemented TODO tickets through canonical SAIPEN
operations.
Priority order:

```
T-1457
T-1454
T-1453
T-1452
T-1456
T-1455

```

T-1451 is a separate inherited fixture repair and does not outrank the active
SRC-100 mission unless it becomes a real closure dependency.
For every candidate:

```
read its exact acceptance
inspect current implementation
reuse existing focused evidence
rerun only the smallest check required to establish CURRENT-tree truth
review the actual diff
terminalize only if the complete acceptance is satisfied

```

Never close a ticket merely because LOG contains a green line.
Never rebuild a fix that is already present just to obtain a fresh-looking diff.
If a ticket cannot close because one acceptance clause is still false:

```
preserve the implementation
keep the ticket open
name the exact remaining clause
continue to its bounded remaining work

```

======================================================================
3. P0 T-1457 — CLOSURE, NOT REIMPLEMENTATION
T-1457 is the current highest-priority workable ticket.
Expected current state:

```
implementation already present
focused controls already green

```

Required action:

```
verify current bytes still satisfy the complete T-1457 acceptance
record current-tree evidence if required by lifecycle
review
close canonically

```

Acceptance must include all of:

```
quoted request extracted correctly with no trailing tokens

trailing:
    --json
    redirect
    pipe
    second flag
    bare request

legacy obligation created before the repair can be discharged by supplying
the request itself

genuine paraphrase remains refused

status exposes:
    obligation
    owed digest
    request digest
    preview
    both canonical discharge commands

```

Do not weaken guard identity matching to make the legacy test green.
Do not close by editing BOARD directly.
======================================================================
4. INTEGRATION BOUNDARY — T-1454 IS NOW THE IMPORTANT SYSTEM BLOCKER
Current validation on the supplied snapshot reports 29 problems.
Of these:

```
26 are runtime-manifest files that exist in this home but are not Git-tracked

3 are current-cycle closure-evidence failures:
    T-1373
    T-1400
    T-1432

```

The runtime-manifest class is directly relevant to T-1454.
Current untracked runtime implementation includes at least:

```
tools/saipen_engine/cold_recovery.py
tools/saipen_engine/metadata_repair.py
tools/saipen_engine/runtime_namespace.py
tools/saipen_engine/supervisor.py
tools/saipen_engine/watchdog.py
tools/saipen_engine/worker.py

```

and their current runtime/test families, including:

```
tools/test_cold_recovery.py
tools/test_conformance_repair_boundary.py
tools/test_metadata_repair.py
tools/test_producer_terminal_consistency.py
tools/test_refusal_registry.py
tools/test_runtime_namespace.py
tools/test_source_multiwork.py
tools/test_source_quarantine_route.py
tools/test_source_refusal_routing.py
tools/test_supervisor.py
tools/test_t1429_deferred_due.py
tools/test_t1452_manifest_authority.py
tools/test_t1453_ingress_clause.py
tools/test_t1454_distribution_blocker.py
tools/test_t1457_ingress_obligation.py
tools/test_user_wait_release.py
tools/test_verify_scope_isolation.py
tools/test_vocabulary_parity.py
tools/test_watchdog.py
tools/test_worker_turnover.py

```

Do not blindly use:

```
git add -A

```

The tree contains a large amount of historical runtime evidence and kitchen
material.
Instead:

```
identify every runtime-manifest path
prove which current Work introduced/owns it
inspect its actual diff/dependency chain
construct an exact reviewed integration scope
keep unrelated evidence/kitchen/history out of the source commit
preserve all foreign or ambiguous dirty material

```

The goal is not "clean Git status at any cost."
The goal is:

```
every manifest-declared runtime file that is part of the current protocol
exists in the committed clone identity

```

and:

```
no unrelated unreviewed bytes are silently swept into the commit

```

======================================================================
5. LOCAL SHIP BOUNDARY FOR THE RUNTIME DELTA
Once the integration scope is proven:

```
run focused tests for the exact runtime cohort

run directly related neighbors

run Ruff on changed Python paths

run validator

```

Expected improvement:

```
runtime-manifest-untracked class -> zero

```

A local commit is allowed only through the canonical reviewed SHIP path.
No:

```
push
tag
release
public publication

```

The source HEAD must advance only after the exact staged scope has been read
back and verified.
After local commit:

```
rerun T-1454 distribution diagnostics

```

Expected:

```
source identity is committed

injection no longer reports "repairs exist only in this working tree"

installed-home freshness can be evaluated against the committed head

```

If an installed home is dirty:

```
do not overwrite it blindly

classify the exact dirty-home condition

leave that home untouched if policy refuses it

continue verification on legally injectable homes

```

T-1454 closes only when its entire declared acceptance is true, not merely when
the error message became more descriptive.
======================================================================
6. THE THREE CLOSURE-EVIDENCE FAILURES ARE DISTINCT
Current validator also reports:

```
T-1373
T-1400
T-1432

```

as DONE without accepted current-cycle closure evidence.
Do not merge these into T-1446.
Do not fabricate PASS.
For each:

```
locate its original acceptance
locate preserved evidence
determine whether a real executable current-tree re-verification exists

```

If the required check remains valid and bounded:

```
use the canonical re-verification mechanism

```

If the old acceptance can no longer be truthfully reproduced:

```
preserve the failure
route it to its existing owner / exact repair class

```

If these failures do not prevent the bounded T-1446 implementation work:

```
classify them as inherited
continue T-1446

```

They must not silently disappear from the final convergence report.
======================================================================
7. CURRENT T-1446 ARCHITECTURE GAP
Do not close T-1446 after the current worker-turnover tests.
The current implementation has:

```
watchdog
lease generations
stale-generation fencing
cold recovery
semantic progress tracker
supervisor observation
supervisor decision
separate worker process
real crash/replace tests
zero-RAM supervisor reconstruction
read-only `saipen autonomy` observability

```

But the current `supervisor.py` explicitly remains a DECIDER, not a launcher.
The public `saipen autonomy` command is explicitly DIAGNOSTIC / read-only.
Therefore the core SRC-100 promise is not complete yet:

```
there is no proven resident execution owner that repeatedly turns supervisor
decisions into unattended worker lifecycle actions

```

A test harness manually spawning three worker processes is valuable evidence.
It is not yet the same thing as:

```
leave SAIPEN running
worker dies
supervisor notices
supervisor fences expired generation
supervisor starts/reassigns replacement
cold state is loaded
exact next action continues
no human presses continue

```

This is the next architectural slice after integration is stable.
======================================================================
8. BUILD ONE EXECUTION OWNER — DO NOT MAKE `saipen autonomy` MUTATING
Preserve:

```
`saipen autonomy`
    read-only diagnostic

```

Do not silently change its effect class from DIAGNOSTIC to EXECUTION.
Introduce or reuse ONE explicit execution surface for unattended supervision.
Its exact command name should follow the existing registry/command grammar.
Required lifecycle:

```
start supervisor run
establish run identity
inspect canonical state
inspect worker lease
choose one supervisor verdict
when mutation is legal:
    launch/adopt exactly one bounded worker generation
monitor heartbeat / process exit
checkpoint progress
on healthy worker:
    never steal
on SUSPECT worker:
    wait according to policy
on EXPIRED worker:
    fence old generation
    acquire new generation
    spawn replacement
on corrupt / ambiguous authority:
    fail closed
    do not spawn a competing mutator
on due human gate:
    park that Work
    continue unrelated eligible Work when legal
on no-progress loop:
    stop burning provider/runtime budget
    emit exact diagnostic action
on project idle:
    stop cleanly

```

The runtime loop must never become a second source of protocol truth.
Canonical Work truth stays in SAIPEN state.
Supervisor runtime state stays derived/runtime-local.
======================================================================
9. WORKER PROCESS CONTRACT
Keep:

```
AGENT IS DISPOSABLE
STATE IS NOT

```

Every worker generation must be bounded.
One worker does not own "finish the whole project."
Its unit remains equivalent to:

```
recover
acquire/adopt legal generation
choose bounded Work slice
reproduce
implement
focused verify
checkpoint
classify
release/continue

```

A dead generation must never be able to mutate after replacement.
The runner must verify the lease generation immediately before any canonical
mutation boundary where stale return is possible.
No second live mutator may pass.
======================================================================
10. PROVIDER / MODEL FAILURE CLASSIFICATION
The source request explicitly includes provider failure behavior.
Add/reuse one closed generic runtime failure vocabulary.
At minimum distinguish:

```
QUOTA_EXHAUSTED
RATE_LIMITED
AUTH_FAILED
PROVIDER_UNAVAILABLE
MODEL_UNAVAILABLE
NETWORK_UNAVAILABLE
HOST_RUNTIME_FAILURE
WORKER_CRASH
UNKNOWN

```

Transient provider/model failure must:

```
preserve Work
preserve checkpoint
release/fence runtime authority as appropriate
record retry timing when known
retry later
or use an already authorized configured fallback

```

Fallback must never:

```
invent credentials
spend unapproved funds
consume reserved quota silently
violate the requested model/provider policy
turn provider failure into protocol corruption

```

Provider failure is not automatically a SAIPEN protocol failure.
======================================================================
11. OBSERVABILITY COMPLETION
The existing autonomy surface is a strong start.
Ensure one read-only observation can expose the real runner state without
opening raw canonical files manually.
Required fields:

```
autonomy run id
supervisor state
worker id
worker generation
lease generation
heartbeat age
current Work
executable Work
phase
bounded slice
elapsed run time
elapsed time since semantic progress
last durable checkpoint
current blocker
deferred gates
due operator actions
provider retry state
no-progress count
exact next action
stop reason

```

The surface must still work when no Work is active.
Do not duplicate STATE/BOARD/LOG into another authority file.
======================================================================
12. CHECKPOINT CADENCE
For a real unattended run:

```
checkpoint after every meaningful bounded slice

```

and:

```
while meaningful active work continues, never allow more than 60 minutes
without durable progress checkpoint evidence

```

A checkpoint must carry enough to reconstruct:

```
Work
phase
slice
last verified result
source/tree identity
evidence identity
blocker/deferred classification
exact next action
progress fingerprint
no-progress count

```

Do not checkpoint every shell command.
No semantic progress for an hour is:

```
NO_PROGRESS

```

not an invented achievement.
======================================================================
13. ACCELERATED CHAOS GATE
Before a one-hour field soak, construct one bounded disposable-project chaos
family.
Cover at least:

```
duplicate continuation/goal ingress
one blocked Work plus one eligible Work
deferred human gate
healthy worker
dead worker
frozen heartbeat
expired lease
old worker returning after replacement
death before checkpoint
death after checkpoint
supervisor restart
cold worker replacement
repeated unchanged expensive test
NO_PROGRESS_LOOP
provider unavailable simulation
explicit user interrupt
all Work genuinely blocked

```

Use the historical T-1449 / T-1450 incident as a deterministic duplicate-ingress
regression shape.
Acceptance:

```
stolen lease count = 0
simultaneous mutator count = 0
lost Work count = 0
lost user Source count = 0
fabricated PASS count = 0
raw canonical manual edit count = 0
false project DONE count = 0
false GLOBAL_STOP count = 0
UNKNOWN terminal failure count = 0

```

Every injected crash/failure must be deliberate and observable.
======================================================================
14. ONE-HOUR REAL SOAK
Only after deterministic chaos is green.
Run a real local unattended supervisor session if the host/runtime supports it.
Do not simulate one hour by altering timestamps.
Require:

```
multiple bounded slices
multiple worker generations
at least one deliberate worker death
at least one blocked/deferred Work
unrelated eligible Work continues after that local block
periodic durable checkpoint
external read-only status observation
zero manual `continue`

```

Measure:

```
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

```

Required zeros:

```
manual_continue_count
duplicate_semantic_mutations
stolen_leases
false_global_stops
fabricated_passes
unknown_terminal_failures
raw canonical manual edits

```

Target:

```
worker replacement <= 5 minutes
cold continuation <= 5 minutes

```

If the current host genuinely cannot supply the required process/provider
runtime:

```
do not fake PASS
record the exact environmental boundary
convert the field gate to a non-seat-holding deferred/external gate

```

======================================================================
15. 24-HOUR FIELD GATE MUST NOT HOLD THE PROJECT HOSTAGE
The 24H gate remains the real SRC-100 field target.
Do not claim it from accelerated tests.
Do not wait inside the mutation seat for 24 hours.
Once implementation, chaos and credible 1H soak are complete:

```
create/reuse the canonical field-gate representation
record exact start conditions
release the mutating seat
surface the field gate as pending/deferred
allow unrelated project work to continue

```

24H acceptance remains:

```
24 real unattended hours

manual_continue_count = 0
duplicate_semantic_mutations = 0
stolen_live_leases = 0
fabricated_pass = 0
unknown_terminal_failure = 0
raw canonical manual edits = 0
false project-wide stops caused by one deferred ticket = 0
active progress checkpoint gap <= 60 minutes
worker/cold recovery <= 5 minutes target

```

Human-only gate:

```
surfaced
parked
unrelated Work continues

```

======================================================================
16. T-1446 TERMINAL CONDITIONS
Do not close T-1446 merely because:

```
supervisor.py exists
worker.py exists
watchdog tests pass
three subprocess generations passed
`saipen autonomy` prints useful JSON

```

Implementation-side closure requires credible proof of:

```
duplicate semantic ingress idempotence
cold recovery
cold worker continuation
semantic progress / no-progress suppression
workability scheduler
due/deferred gate semantics
lease liveness and fencing
real supervisor execution owner
worker replacement
supervisor restart
provider/runtime failure classification
observable status
chaos gate
credible one-hour soak or one exact truthful environmental boundary

```

The 24H field gate must be:

```
PASS

```

or:

```
explicitly deferred as one real external/runtime gate that does not hold the
mutation seat

```

No "basically passed."
======================================================================
17. RESUME T-1428 WHEN T-1446 STOPS HOLDING THE SEAT
T-1428 remains blocked on T-1446.
When:

```
T-1446 is terminal

```

OR:

```
all implementation work is complete and only a non-seat-holding 24H field
observation remains

```

resume the existing:

```
T-1428 / SRC-083

```

Do not create another roadmap.
Do not pull historical T-1428 broad-family failures into T-1446 unless one
specific failure blocks the autonomy implementation.
======================================================================
18. T-1451
T-1451 is an inherited stale cohort-publication fixture.
Current measured issue:

```
test_control_c_d_cohort_cli_and_publication predates mandatory release-scope
ship gating

```

Repair only through its existing ticket.
Required:

```
current publication control green under the present release-scope contract

red control proves a scope-free ship still refuses

```

Do not weaken the release-scope gate merely to make the stale fixture pass.
This is secondary to T-1454/T-1446 unless it blocks a required integration gate.
======================================================================
19. EXPENSIVE TEST BUDGET
For each bounded change:

```
reproduce RED
smallest focused GREEN
necessary neighbors
review

```

Run broad expensive families only at meaningful convergence boundaries.
Before any long test ask mechanically:

```
what changed?
what hypothesis does this run test?
what new evidence can it produce?

```

If the answer is identical to the previous run:

```
do not rerun it

```

The historical T-1449 bounded timeout remains evidence.
Do not rerun it unchanged.
======================================================================
20. HARD STOPS
Stop mutation only for:

```
security/integrity P0 making further mutation unsafe
irreversible destructive action lacking authority
genuine ambiguous mutation authority that cannot be resolved safely
all eligible Work externally blocked
genuine human decision with no unrelated eligible Work
evidence that the autonomy architecture itself is unsafe
missing runtime capability required for the next real field gate

```

One blocked ticket is not a project-wide stop.
One deferred ticket is not a project-wide stop.
One unavailable provider is not automatically a project-wide stop.
One old broad test red is not automatically a project-wide stop.
======================================================================
21. PUBLICATION BOUNDARY
Allowed:

```
local reversible implementation
focused tests
deterministic chaos tests
local reviewed commits when canonical SHIP requires them
installed-home synchronization under existing safe injection rules

```

Not allowed without new authority:

```
push
tag
GitHub Release
public package publication
unapproved paid provider usage
reserved quota consumption

```

Autonomy acceptance is not publication authority.
======================================================================
22. REQUIRED FINAL REPORT
At genuine session end report exactly:

```
STATUS

ACTIVE WORK

HEAD

LAST EVENT

T-1457 STATUS

T-1454 STATUS

T-1453 STATUS

T-1452 STATUS

T-1456 STATUS

T-1455 STATUS

T-1451 STATUS

RUNTIME MANIFEST UNTRACKED COUNT

CLOSURE-EVIDENCE REDS

INSTALLED-HOME FRESHNESS

SUPERVISOR EXECUTION OWNER STATUS

CHAOS GATE STATUS

ONE-HOUR SOAK STATUS

24H FIELD GATE STATUS

MANUAL CONTINUE COUNT

WORKER GENERATION COUNT

CRASH RECOVERY COUNT

STOLEN LEASE COUNT

DUPLICATE SEMANTIC MUTATION COUNT

FALSE GLOBAL STOP COUNT

FABRICATED PASS COUNT

UNKNOWN TERMINAL FAILURE COUNT

MAXIMUM RECOVERY LATENCY

T-1446 CLOSURE STATUS

T-1428 RESUME STATUS

PUBLICATION STATUS

EXACT NEXT ACTION

DO_NOT_REPEAT

```

The exact next action must be executable.
Do not end with a question.
Do not end with `cc all`.
Do not report T-1446 DONE while the system still requires a human to translate
a supervisor verdict into worker replacement.
The governing invariant remains:

```
AGENT IS DISPOSABLE.
STATE IS NOT.

```
