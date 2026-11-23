SAIPEN

SAIHANDOFF — ROOT-CAUSE RESPONSE SURFACE / OPERATOR AUTHORITY HARDENING

TARGET MODEL
Sol 6.1

EFFORT
Max

EXECUTION MODE
Long-horizon autonomous implementation.

QUALITY > TIME.

Work for as long as useful.

Do not stop after the first locally green patch.

Do not produce progress narration unless a genuine human-only boundary requires
operator action.

Do not push, publish, tag, release, rewrite remote history or perform an external
irreversible action without explicit operator authority.

======================================================================
MISSION
======================================================================

SAIPEN still allows agents to write human-visible "novels" even though the
protocol already contains:

    STYLE.md compression
    EXEC-RESPONSE-01
    response_surface
    chat_style
    HUSH / silent execution
    host response hooks
    detail authorization
    evidence journals

This means the system has substantial machinery but does not yet enforce the
operator's actual desired UX as one coherent invariant.

The desired behavior is:

    IF WORK CAN CONTINUE:
        CONTINUE WORK.
        SAY NOTHING.

    IF WORK STOPS BECAUSE THE HUMAN MUST ACT:
        SAY ONLY WHAT THE HUMAN NEEDS TO ACT.

    IF WORK COMPLETES:
        RETURN A SMALL RESULT DIGEST.

    IF THE HUMAN EXPLICITLY REQUESTS A DEEP REPORT:
        RETURN A BOUNDED DETAILED REPORT.

Everything else belongs in:

    LOG
    evidence
    structured state
    machine artifacts
    durable reports

not in default chat.

The human chat surface is a CONTROL SURFACE.

It is not the canonical database.

======================================================================
IMPORTANT: DO NOT PATCH FIRST
======================================================================

First reconstruct the exact current behavior.

Find the causal chain.

Then repair the narrowest canonical owners.

Do not begin by:

    lowering a random character constant;
    adding another prompt sentence;
    adding another adapter-specific regex;
    special-casing one Estonian report;
    banning tables globally;
    hiding evidence;
    truncating output blindly;
    moving prose into code fences;
    moving prose into DETAILS;
    weakening validation;
    declaring unsupported hosts "mechanical".

This target requires architectural convergence, not cosmetic shortening.

======================================================================
CURRENT SNAPSHOT TO VERIFY FIRST
======================================================================

The latest supplied project snapshot was observed with:

    STATE
        phase: SCOUT
        task: T-1599
        next_action: PHASE SCOUT T-1599
        blocker: none
        execution_intent: goal

    BOARD DOING
        T-1599 [P1] test1
        user_explicit: true
        source_receipts: SRC-164
        owner: saipen-cli

    BOARD TODO includes:
        T-1464
        T-1494

    T-1510 was parked behind T-1599.

Do not trust this handoff's snapshot over current machine truth.

At start:

    inspect STATE
    inspect BOARD
    inspect LOG
    inspect source intake
    inspect git/worktree
    inspect installed adapter generation

If the current tree moved since this handoff:

    preserve the newer canonical truth.

But specifically investigate T-1599/SRC-164 if they still exist or if their
history remains.

======================================================================
PART A — FALSE OPERATOR AUTHORITY INCIDENT
======================================================================

The current snapshot contains an extremely valuable real defect carrier.

SRC-164 body:

    test1

SRC-164 metadata records approximately:

    source_kind: user_instruction

    request_provenance:
        witness: model_supplied

        note:
            no operator carrier and no transport obligation;
            the stored bytes are what this session supplied,
            and nothing compared them with what the operator wrote

Its contract currently contains:

    clauses: {}

Its coverage currently contains:

    requirements: {}

Despite that, the protocol projected:

    T-1599 [P1] test1
    user_explicit: true

and then recorded:

    user request SRC-164 projected as T-1599 (user_explicit)

    goal pivot -- T-1599 (SRC-164): test1

    T-1510 blocked:
        PAUSED by user request SRC-164

    T-1599 claimed

Therefore the actual machine behavior was:

    MODEL-SUPPLIED BYTES
        +
    NO OPERATOR CARRIER
        +
    NO TRANSPORT OBLIGATION
        +
    ZERO CLAUSES
        +
    ZERO REQUIREMENTS

        ->

    USER_EXPLICIT P1 AUTHORITY
        -> GOAL PIVOT
        -> PREEMPT LEGITIMATE WORK
        -> CLAIM SEAT

That is not merely a bad classifier result.

That is an authority escalation.

======================================================================
PART A1 — HISTORICAL CONTROL: SRC-146 / T-1573
======================================================================

There is an even stronger historical carrier.

SRC-146 also contains:

    test1

Its provenance is also:

    witness: model_supplied

Historical LOG explicitly recognized it as:

    INVALID_INVOCATION

with reasoning equivalent to:

    no requested change
    no target
    no acceptance
    nothing to implement or verify

However later history moved T-1573 through:

    BUILD
    VERIFY
    REVIEW
    SHIP
    DONE

by treating its empty requested change set as an "accept-empty" ticket.

That means there may be TWO related defects:

DEFECT A:

    untrusted/model-supplied ingress can obtain `user_explicit` authority.

DEFECT B:

    an invocation already known to contain no Work can remain a lifecycle
    vehicle and eventually reach DONE instead of receiving a non-work terminal
    disposition.

Do not assume they have the same owner.

Trace both.

======================================================================
PART A2 — KNOWN CODE SMELL TO VERIFY
======================================================================

Current `operator_task.py` intentionally distinguishes:

    operator_carrier
    transport_obligation
    model_supplied

Its documentation correctly says that `model_supplied` means nobody compared
the session's supplied bytes with the operator's actual text.

It also intentionally does NOT reject `model_supplied`.

That is reasonable as a persistence fact.

The dangerous transition appears later.

Current start/entry flow appears to do roughly:

    operator_task.witness(...)
        -> model_supplied accepted

    intake.capture(...)
        -> source_kind user_instruction

    _project_user_request(...)
        -> BOARD row writes:
             user_explicit: true

    new projected Work
        -> set_goal_intent(...)

The projection does not appear to preserve the distinction between:

    "these bytes were captured"

and:

    "these bytes carry trusted operator authority".

Prove the exact code path.

Do not rely only on this handoff's reading.

======================================================================
PART A3 — AUTHORITY MODEL
======================================================================

Establish one explicit machine truth:

    SOURCE PERSISTENCE
        !=
    OPERATOR AUTHORITY

A source may be durably stored without being authorized to:

    preempt active Work;
    pivot /goal;
    become P1 merely by arrival;
    set user_explicit:true;
    supersede trusted operator intent;
    retire Work;
    widen execution authority;
    reset a safety valve;
    authorize detailed output;
    authorize external actions.

The provenance class must matter at the authority boundary.

Do NOT implement:

    if witness == model_supplied:
        refuse everything

That would break ordinary hosts where exact operator ingress is currently not
transport-verifiable.

Instead design explicit capability semantics.

Possible conceptual states:

    TRUSTED_OPERATOR
    TRANSPORT_BOUND_OPERATOR
    UNWITNESSED_SESSION_INGRESS

Use existing names/contracts where possible.

Do not create duplicate vocabulary merely because these names are convenient.

======================================================================
PART A4 — SAFE SEMANTICS FOR UNWITNESSED INGRESS
======================================================================

Solve the usability problem honestly.

A host without a trusted operator carrier still needs to function.

But lack of a trusted carrier must not silently become trusted authority.

Investigate and choose a coherent rule such as:

    MODEL_SUPPLIED / UNWITNESSED ingress may be captured durably.

    It may possibly become candidate/local Work when the project is idle,
    if the protocol explicitly accepts that degraded mode.

    It must NOT preempt an already active Work trajectory merely because the
    model typed it into `saipen start`.

    It must NOT become `user_explicit:true` unless that field truthfully means
    exactly the authority level it carries.

    It must NOT reset bounded authority.

    It must NOT override a trusted operator objective.

    It must NOT claim an external human decision.

Do not adopt these exact semantics blindly.

Derive the smallest coherent authority model from existing SAIPEN contracts.

Critical requirement:

    authority strength must never silently increase during projection.

======================================================================
PART A5 — HOST CAPABILITY REALITY
======================================================================

Determine which hosts can establish trusted ingress and which cannot.

Existing architecture includes mechanisms such as:

    operator task digest/file carrier
    pending ingress transport obligation
    Claude UserPromptSubmit
    launch environment binding
    host adapters

Inspect each supported host.

For each host record whether it can prove:

    exact operator ingress
    before Work projection

Do not pretend that an unavailable transport exists.

If a host cannot prove operator ingress:

    report that capability honestly;
    use degraded authority semantics.

This is similar to protocol admission:

    honesty is better than fake HARD enforcement.

======================================================================
PART A6 — CURRENT T-1599 RECOVERY
======================================================================

If T-1599 still exists as active Work, do not implement "test1".

Do not close it as an implementation success.

Do not fabricate evidence for it.

Do not manually edit:

    STATE.md
    BOARD.md
    LOG.md

Determine the canonical disposition.

The semantic result should be equivalent to:

    INVALID_INVOCATION
    NON_WORK
    FALSE_AUTHORITY_PROJECTION

using existing canonical vocabulary if one already owns the case.

SRC-164 must remain preserved for forensic evidence.

Required current-state outcome:

    T-1599 no longer owns an implementation seat;
    no fake code delta exists;
    no fake DONE implementation claim exists;
    SRC-164 remains historically visible;
    T-1510 is released from the false dependency;
    the legitimate trajectory resumes coherently.

If current recovery cannot undo this without manual protected-file mutation:

    that is a protocol recovery defect.

Repair the canonical route.

======================================================================
PART A7 — EXACT AUTHORITY REGRESSIONS
======================================================================

Preserve the real carriers.

CASE A

    body:
        test1

    provenance:
        model_supplied

    clauses:
        0

    requirements:
        0

    active legitimate Work exists.

Expected:

    may persist diagnostically;
    must not obtain trusted operator preemption authority;
    must not pivot goal;
    must not become a P1 user-explicit implementation objective.

CASE B

Same literal body, but a trusted external operator carrier proves those exact
bytes.

Expected:

    provenance strength is different.

Do NOT hard-code:

    "test1 is invalid"

Content alone is not the authority oracle.

CASE C

Model-supplied real-looking request:

    refactor authentication and run all tests

with no carrier.

Expected:

    authority remains explicitly unwitnessed;
    no silent promotion to trusted operator authority.

CASE D

Trusted operator request with identical text.

Expected:

    normal trusted path.

CASE E

Model-supplied ingress while project is idle.

Expected:

    behavior matches the deliberately chosen degraded-mode policy and is
    mechanically distinguishable from trusted operator Work.

CASE F

Model-supplied ingress while another ticket is active.

Expected:

    cannot silently preempt that ticket as human authority.

CASE G

Previously classified INVALID_INVOCATION.

Expected:

    cannot later drift through BUILD/VERIFY/SHIP/DONE as if it were a normal
    implementation ticket unless a real later authority event changes its
    classification.

======================================================================
PART B — THE ACTUAL "ROMAN" PROBLEM
======================================================================

After restoring truthful authority/current Work, attack the response problem at
its root.

The latest agent report is a real example.

It began compactly:

    Peatusin. Täiesti lõpetatud on T-1598 ...

but then expanded into:

    what was completed;
    detailed root cause;
    implementation explanation;
    exact commit IDs;
    test evidence;
    validation evidence;
    two unfinished acceptance details;
    full 54-row BLOCKED classification;
    current git history;
    current STATE;
    detailed continuation instructions.

Most facts were useful.

Most did NOT belong inline in default chat.

This distinction is critical:

    INFORMATION MAY BE IMPORTANT
        AND
    STILL NOT BELONG IN DEFAULT CHAT.

======================================================================
PART B1 — ROOT UX CONTRACT
======================================================================

Implement one canonical human-surface contract.

Default:

    runnable work:
        NO user-visible model prose

    successful completion:
        tiny digest

    user-issued stop:
        tiny handback

    genuine human blocker:
        bounded action-oriented explanation

    safety/external-authority boundary:
        bounded action-oriented explanation

    explicit request for full forensic/detail:
        larger bounded report

Everything else:

    persist.

The final response should answer:

    What happened?
    Is it done?
    Is something blocked?
    Do I need to do anything?
    What happens next?

It should NOT answer by default:

    every implementation detail;
    every commit;
    every evidence ID;
    every blocker row;
    every intermediate decision;
    every test group;
    the whole journey.

======================================================================
PART B2 — CURRENT CONTRACTS TO INSPECT
======================================================================

Current implementation already contains useful pieces.

Do not replace them blindly.

Inspect:

    saipen/STYLE.md
    saipen/EXECUTION.md
    tools/saipen_engine/response_surface.py
    tools/saipen_engine/chat_style.py
    tools/saipen_engine/hush.py
    tools/saipen_engine/protocol_admission.py
    host adapters / guards
    adapter registry

Known current facts to verify:

STYLE ordinary chat:

    chat prose <= 5 lines
    absolute max 8

EXEC-RESPONSE current field budgets roughly include:

    RESULT <= 3 lines / 720 chars
    BLOCKER <= 1 / 300
    OPERATOR ACTION <= 1 / 300
    NEXT EXACT ACTION <= 1 / 240
    VALIDATION <= 5 / 480
    EFFICIENCY <= 1 / 240
    DETAILS <= 8 / 2400

Whole operational boundary:

    ordinary <= 2000 chars
    detailed <= 4400 chars

HUSH currently carries:

    FINAL_REPORT_MAX_LINES = 20

These contracts are individually defensible but may not compose into the UX the
operator wants.

Measure actual rendered outputs.

Do not debate constants abstractly.

======================================================================
PART B3 — IMPORTANT CURRENT DETAIL-AUTHORIZATION HOLE
======================================================================

Inspect `detail_mode_for_request`.

Current grammar appears to treat phrases equivalent to:

    give me a summary
    give me a brief
    give me a final report

as EXPLICIT_REPORT because the grammar accepts:

    report
    write-up
    summary
    brief

with an optional adjective.

This is semantically backwards for compression.

A request for:

    summary
    brief
    quick update
    short status

must NOT expand the response budget.

"Brief" should not unlock a larger essay.

"Summary" should not unlock 4400 characters.

Distinguish at minimum:

COMPACT SUMMARY INTENT:

    summary
    brief
    quick update
    short report
    what happened
    status
    where are we

from:

EXPLICIT DEEP DETAIL INTENT:

    detailed report
    full forensic report
    complete audit with all evidence
    verbose technical write-up
    full handoff
    detailed handoff

Do not blindly key on one noun.

Authorization should depend on explicit semantic request for depth.

======================================================================
PART B4 — MULTILINGUAL DETAIL AUTHORITY
======================================================================

The operator routinely uses Russian.

The project may reply in Estonian because STYLE currently pins:

    reply_language: et

Those are separate concerns.

Current detail authorization appears heavily English-oriented.

Fix this honestly.

Detail authorization should recognize deliberate explicit depth requests in the
supported human ingress languages where SAIPEN claims support:

    English
    Estonian
    Russian

But do NOT broaden so much that ordinary phrases accidentally unlock essays.

Examples that should remain COMPACT:

EN:
    give me a summary
    brief update
    what happened?
    where are we?
    status
    tell me the result

RU:
    дай сводку
    краткий отчёт
    что там?
    что сделал?
    где мы?
    статус
    что получилось?

ET:
    anna kokkuvõte
    lühike raport
    mis juhtus?
    kus me oleme?
    staatus

Examples that may authorize DEEP DETAIL:

EN:
    give me a detailed forensic report with all evidence
    produce a full technical audit
    write a complete implementation handoff

RU:
    дай подробный форензик-отчёт со всеми доказательствами
    сделай полный технический аудит
    дай полный детальный хендофф

ET:
    anna täielik detailne tehniline aruanne koos tõenditega
    tee täielik audit
    anna detailne täielik handoff

Use bounded closed grammars.

Negation and quotation must not authorize detail.

======================================================================
PART B5 — RESPONSE CLASSES, NOT ONE UNIVERSAL BUDGET
======================================================================

The response surface should know WHY a message is being emitted.

Design/reuse canonical response classes approximately equivalent to:

    SILENT_CONTINUATION

    COMPACT_FINAL

    STOP_HANDBACK

    HUMAN_ACTION_BLOCKER

    SAFETY_BOUNDARY

    EXPLICIT_DETAILED_REPORT

Exact names are implementation-owned.

Do not create names merely for aesthetics.

The important property:

    each class has explicit allowed content
    and an explicit budget.

A stop handback should not inherit the same budget as a detailed audit.

A normal DONE should not inherit the same budget as a human blocker.

======================================================================
PART B6 — TARGET HUMAN BUDGETS
======================================================================

Re-derive final constants from real fixtures.

Do not copy these numbers blindly.

Desired UX is approximately:

SILENT_CONTINUATION

    0 visible prose

COMPACT_FINAL

    preferably <= 5-6 visible content lines
    preferably <= 600-900 chars

STOP_HANDBACK

    preferably <= 5-6 visible content lines
    preferably <= 600-900 chars

HUMAN_ACTION_BLOCKER

    preferably <= 6-8 visible content lines
    preferably <= 900-1200 chars

EXPLICIT_DETAILED_REPORT

    larger but still bounded

The exact schema may include labels.

Count actual rendered visual weight, not merely "field content lines" while
ignoring twelve visible heading/value lines.

The operator should normally be able to read the whole default reply without
scrolling through a miniature technical memoir.

======================================================================
PART B7 — DO NOT PRESERVE FORMAT BY DOGMA
======================================================================

EXEC-RESPONSE currently uses mandatory vertical headings.

Preserve the SEMANTICS:

    status
    result
    blocker
    operator action
    next action
    validation

But evaluate whether the current vertical rendering itself contributes
unnecessary visual bulk.

Do not casually break the schema.

But also do not defend a noisy rendering merely because tests currently encode
it.

Possible acceptable result:

    STATUS: DONE
    RESULT: T-1598 fixed; T-1510 resumed.
    VALIDATION: CURRENT_PASS | 4728 green
    NEXT: T-1510 continues automatically.

This is only an illustration.

Do not freeze this syntax unless the evidence supports it.

One canonical renderer must own the final form.

Adapters must not independently invent presentation.

======================================================================
PART B8 — STOP SEMANTICS
======================================================================

`saipen stop` is a major regression target.

Stopping means:

    execution stops;
    state is preserved;
    the operator receives a handback.

It does NOT mean:

    write the session memoir.

Default STOP output needs only:

    what completed;
    what is still active;
    why execution stopped;
    whether validation is current;
    exact human action if required;
    exact next execution position.

Do NOT inline by default:

    complete root cause;
    commit list;
    every evidence hash;
    blocker inventory;
    every test command;
    every repaired defect;
    entire git status;
    entire STATE dump;
    complete next plan.

Persist those elsewhere.

======================================================================
PART B9 — EVIDENCE OVERFLOW
======================================================================

Create/reuse a canonical overflow rule:

    REQUIRED FOR AUDITABILITY
        but
    NOT REQUIRED FOR IMMEDIATE HUMAN DECISION

        -> STORE, DO NOT NARRATE.

Possible durable owners:

    LOG
    .saipen/evidence
    structured final-report JSON
    validation record
    ticket detail_ref

The visible reply may say:

    validation: CURRENT_PASS, 4728 checks, evidence recorded

instead of dumping:

    every verifier
    every hash
    every record path
    every evidence pair

Evidence completeness must stay 100%.

Chat duplication may approach zero.

======================================================================
PART B10 — LARGE COLLECTIONS
======================================================================

The 54-BLOCKED table is a perfect test.

Default chat should show something like:

    54 blockers remain:
      20 strategic
      11 external authority
      7 recoverable
      6 capability
      ...

The complete ticket list belongs in evidence/state.

Unless the user explicitly asks:

    list every remaining blocker

do not inline every ticket.

Apply the same rule to:

    test failure lists;
    changed file lists;
    commit lists;
    evidence lists;
    worker lists;
    source receipt lists;
    warning lists.

Summarize by default.

Expand on explicit request.

======================================================================
PART B11 — SEMANTIC DUPLICATION
======================================================================

Character limits alone do not solve novels.

A response can repeat the same fact in:

    RESULT
    VALIDATION
    DETAILS
    prose clarification
    next-step recap

and remain under individual field limits.

Create/reuse semantic normalization rules so one fact has one human-facing owner.

Examples:

Ticket completion:

    RESULT

Validation numbers:

    VALIDATION

Human-only blocker:

    BLOCKER

What the human must do:

    OPERATOR ACTION

What the system will do next:

    NEXT

Implementation root cause:

    evidence / DETAILS only when explicitly authorized

Do not repeat one fact in three fields for "clarity".

======================================================================
PART B12 — MACHINE STATE SHOULD GENERATE HUMAN DIGEST
======================================================================

Prefer deriving final output from canonical structured state.

Do not let the model freely author a retrospective and then merely run length
checks afterward.

Investigate a stronger pattern:

    canonical machine state
        ->
    typed response facts
        ->
    canonical compact renderer
        ->
    final response gate

rather than:

    model writes essay
        ->
    regex decides whether essay is too long.

The model may provide bounded field content where unavoidable.

But state already knows much of:

    task
    phase
    blocker
    validation
    next action
    operator_due
    efficiency

Use machine truth.

Do not ask the model to restate facts the engine already owns.

======================================================================
PART B13 — RESPONSE GATE MUST NOT AUTHORIZE ITSELF
======================================================================

Preserve and strengthen this invariant:

    outgoing text never authorizes outgoing detail.

Only trusted HUMAN ingress may authorize detailed mode.

Model reasoning such as:

    "this is important"
    "the user deserves transparency"
    "the root cause needs explanation"
    "there were many changes"
    "this deserves a detailed answer"
    "I should be complete"

has ZERO authority effect.

Build explicit adversarial tests for those reasoning outcomes.

======================================================================
PART B14 — INTERMEDIATE NARRATION
======================================================================

Final-response compactness is only half the UX.

Current adapter registry honestly says many hosts have:

    silent_tool_continuation: ADVISORY
    intermediate_text_suppression: ADVISORY

Do not falsely claim otherwise.

Still strengthen the portable contract:

    continue/goal/run
        -> no discretionary model progress prose

unless the human explicitly requested progress.

Machine heartbeat goes to:

    LOG
    status
    runtime telemetry
    UI

not chat.

Explicit progress authorization should remain bounded.

A progress request is not permanent authority for every later turn.

======================================================================
PART B15 — HOST ENFORCEMENT MATRIX
======================================================================

Audit every supported host against actual capabilities.

At minimum current registry contains distinct behavior for:

OpenCode

    completed-text-part mechanical final/style gate
    intermediate suppression advisory

Claude

    prompt-level delivery capability
    Stop mechanical response/style correction
    Stop re-entry limitation
    intermediate suppression advisory
    hard admission unavailable without separated authority

Codex

    Stop mechanical response/style correction
    no pre-output interception
    hook trust requirement
    Stop re-entry limitation
    intermediate suppression advisory

ZAICODE / production ZCode

    response enforcement advisory
    style enforcement advisory
    no installed final-response hook

Do not overstate any host.

Critical distinction:

    DETECT AFTER TEXT EXISTS
        !=
    PREVENT USER FROM EVER SEEING TEXT.

If Codex/Claude Stop operates after the text is already rendered:

    say so in registry/capability truth.

Do not label the UX "hard invisible prevention".

For hosts with only advisory enforcement:

    maximize instruction quality;
    use canonical generated contracts;
    detect where possible;
    keep capability truth honest.

======================================================================
PART B16 — INSTALLED GENERATION / STALE GUARDS
======================================================================

Previous incidents proved that source can be correct while installed host homes
remain stale.

Therefore response acceptance must include:

    source artifact current;
    installed artifact current;
    adapter registry current;
    status reports actual effective enforcement.

Do not close based only on repository tests if the real supported host runs a
different installed generation.

For each mechanically supported host:

    verify source hash
    verify installed hash
    verify hook active/trusted where required
    run a real/synthetic host boundary test through the installed route where
    the existing test harness supports it.

Do not manufacture trust.

======================================================================
PART C — CURRENT LEGITIMATE WORK T-1510
======================================================================

The previous handback stated that T-1510 still needed:

    a fresh core_unit evidence run after final BOARD changes;

    a second blocker reconciliation pass proving zero changes.

After false T-1599 authority is removed:

    inspect current T-1510 acceptance.

If these obligations still remain:

    finish them.

Do not rely on the prose report as evidence.

Do not duplicate tests if newer canonical evidence already satisfies the same
oracle.

Once T-1510 is truly complete:

    close it through the normal lifecycle.

Then continue the response-surface work.

======================================================================
PART D — RELATED EXISTING WORK
======================================================================

Before creating new tickets inspect historical/current owners including:

    T-1553
    T-1556
    T-1557
    T-1558
    T-1567
    T-1568
    T-1569
    T-1583
    T-1584

Do not reopen DONE Work merely because a new incident appeared.

Determine whether the incident means:

    old acceptance was incomplete;

or:

    a genuinely new uncovered layer now exists.

Prefer a narrow successor ticket when history is already terminal.

Also inspect:

    T-1494

but do NOT let continuation-authority work consume this target unless it is
directly required.

T-1494 is strategically important but is a separate concern:

    persistent /goal
    bounded authority
    safety valve continuation

Do not mix anti-roman response enforcement with goal-duration semantics merely
because both involve "authority".

======================================================================
PART E — REAL REGRESSION FIXTURES
======================================================================

Use real incidents, not only toy strings.

REGRESSION 1 — FALSE AUTHORITY

    SRC-164
    body: test1
    witness: model_supplied
    no carrier
    no obligation
    clauses: 0
    requirements: 0

Expected:

    cannot become trusted preemptive operator authority.

REGRESSION 2 — HISTORICAL NON-WORK DRIFT

    SRC-146 / T-1573

Expected:

    INVALID/NON_WORK classification cannot later become a fake implementation
    DONE merely to free the seat.

REGRESSION 3 — LONG STOP HANDBACK

Use the actual T-1598 report content.

Expected:

    default stop reply becomes compact.

The complete underlying evidence remains available.

REGRESSION 4 — LARGE BLOCKER SET

    54 blocker rows

Expected:

    compact class counts by default;
    complete rows only on explicit request.

REGRESSION 5 — EVIDENCE FLOOD

    dozens/hundreds of evidence records

Expected:

    final chat size does not grow linearly with evidence count.

REGRESSION 6 — MANY COMMITS

Expected:

    default reply does not enumerate commit history.

REGRESSION 7 — MANY TEST GROUPS

Expected:

    aggregate PASS/FAIL/new_red plus important exception only.

======================================================================
PART F — ADVERSARIAL REQUEST MATRIX
======================================================================

Test exact human intent classes.

1.

Human:

    continue

Expected:

    execute silently.

No progress essay.

2.

Human:

    keep going until done

Expected:

    continue silently.

Not detail authorization.

3.

Human:

    stop

Expected:

    compact STOP_HANDBACK.

4.

Human:

    what happened?

Expected:

    compact explanation.

5.

Human:

    give me a summary

Expected:

    compact.

NOT explicit detail mode.

6.

Human:

    give me a brief

Expected:

    compact.

NOT explicit detail mode.

7.

Human:

    give me a final report

Determine desired contract carefully.

A normal "final report" should probably remain compact unless explicit depth is
requested.

Do not preserve current behavior solely because current grammar grants detail.

8.

Human:

    give me a detailed forensic report with all evidence

Expected:

    explicit detailed mode.

9.

Human:

    explain everything in full detail including evidence and root cause

Expected:

    explicit detailed mode if grammar deliberately supports it.

10.

Human:

    do not give me a detailed report, just fix it

Expected:

    no detail authorization.

11.

Human quotes:

    The bug is that "give me a detailed report" triggers something.

Expected:

    quoted phrase does not authorize detail.

12.

Human:

    дай сводку

Expected:

    compact.

13.

Human:

    дай краткий отчёт

Expected:

    compact.

14.

Human:

    дай полный подробный технический отчёт со всеми доказательствами

Expected:

    explicit detail.

15.

Human:

    что там?

Expected:

    compact.

16.

Human:

    anna kokkuvõte

Expected:

    compact.

17.

Human:

    anna täielik detailne tehniline aruanne koos tõenditega

Expected:

    explicit detail.

======================================================================
PART G — RESPONSE CONTENT MATRIX
======================================================================

For each response class test these payload pressures:

    0 findings
    1 finding
    10 findings
    100 findings

    0 blockers
    1 blocker
    54 blockers

    1 test group
    20 test groups

    1 commit
    20 commits

    short ticket
    long ticket description

    no evidence
    hundreds of evidence records

Default response size must remain approximately O(1) with respect to evidence
volume.

Do not let human chat scale linearly with internal state size.

======================================================================
PART H — FAILURE BEHAVIOR
======================================================================

If response compression itself fails:

    do not dump the oversized original.

Prefer:

    canonical compact fallback

containing:

    status
    failure code
    operator action if any
    evidence location

The response system must fail compactly.

Do not create:

    "response too long" followed by a 40-line explanation of why it was too long.

======================================================================
PART I — DETAILS MUST NEVER BECOME A TRASH CAN
======================================================================

DETAILS is not:

    "everything else".

When explicit detail is authorized, it still needs structure and a budget.

Deep reports should prefer:

    summary
    key findings
    evidence references

over:

    chronological tool narration.

Even explicit detailed mode should not reproduce machine logs wholesale.

If the user explicitly requests raw logs:

    provide or reference the actual artifact.

Do not paraphrase thousands of lines.

======================================================================
PART J — DO NOT BREAK SOPHISTICATED REQUESTS
======================================================================

The operator frequently requests large copy-ready artifacts:

    SAIHANDOFF
    audits
    Future Gates
    implementation specs
    roadmaps

Those are intentionally detailed deliverables.

Do not make Anti-Roman accidentally truncate artifacts the user explicitly
asked to copy and send elsewhere.

Distinguish:

    chat response about work

from:

    requested artifact content.

An explicitly requested handoff may be large.

The surrounding chat should still remain small.

This is crucial.

Anti-Roman means:

    no unsolicited novels.

It does NOT mean:

    destroy intentionally requested technical documents.

======================================================================
PART K — COPY-READY / ARTIFACT BOUNDARY
======================================================================

A requested handoff/audit/spec is an artifact-like payload.

It may intentionally exceed ordinary chat prose budgets.

The authorization must be explicit and typed.

Examples:

    "give me a full handoff"
    "write the audit"
    "prepare the implementation spec"

may authorize that artifact.

But:

    "what happened?"
    "give me a summary"
    "stop"
    "continue"

must not.

Do not infer artifact authorization merely because the model thinks a handoff
would be useful.

======================================================================
PART L — ONE CANONICAL OWNER
======================================================================

Avoid another generation of contract drift.

Target architecture:

    human ingress
        ->
    ingress provenance / authority class
        ->
    execution policy
        ->
    response reason/class
        ->
    detail authorization
        ->
    typed response facts
        ->
    canonical renderer
        ->
    canonical classifier
        ->
    host adapter enforcement

One owner per fact.

Adapters transport.

Adapters do not redefine.

STYLE owns voice.

EXECUTION owns operational behavior.

Response Surface owns response shape/budgets.

Ingress authority owner owns who may change execution objective.

Do not create parallel copies.

======================================================================
PART M — RED-FIRST REQUIREMENT
======================================================================

For every root defect:

    capture SAME-INCIDENT RED before relying on GREEN.

Required at minimum:

    false authority projection RED;
    non-work lifecycle drift RED;
    T-1598 long stop report RED;
    summary/brief detail-authorization RED;
    model self-justified detail RED;
    large blocker inventory RED.

Then implement.

Then run the SAME oracle.

Do not change verifier and subject together in a way that makes the RED
meaningless.

======================================================================
PART N — VALIDATION
======================================================================

Focused verification is necessary but not sufficient.

Required before final closure:

    relevant unit tests;
    response-surface tests;
    chat-style tests;
    hush tests;
    admission layering tests;
    adapter parity;
    Codex guard tests;
    Claude guard tests;
    OpenCode style/response tests;
    ZCode production boundary tests;
    ingress/operator-task tests;
    source/intake tests;
    router/pick-rule tests;
    recovery tests affected by current T-1599 repair;
    refusal registry;
    protocol registry;
    fail-site inventory if affected;
    scenario suite if the changed surfaces participate in it;
    canonical validate;
    full declared core family.

Final full core:

    red = 0
    new_red = 0

Do not baseline regressions.

Do not weaken tests simply to fit the new design.

======================================================================
PART O — INSTALLED-HOST DOGFOOD
======================================================================

Where technically possible, dogfood the final behavior.

At minimum prove:

    normal continue produces no discretionary narration;

    normal completion is compact;

    stop handback is compact;

    explicit detailed request can still produce a bounded detailed report;

    ordinary summary remains compact;

    large evidence set does not inflate default chat;

    model-supplied probe cannot preempt trusted Work.

If a real host cannot mechanically enforce one of these:

    record the capability boundary honestly.

Do not fake evidence.

======================================================================
PART P — LONG-HORIZON IMPROVEMENT PASS
======================================================================

After exact incidents are fixed, perform a bounded adjacent sweep.

Search for:

    another way to set user_explicit without provenance;
    another way to goal-pivot from unwitnessed source;
    another response path bypassing canonical classifier;
    another detail-mode derivation outside canonical owner;
    adapter-specific response limits;
    another field that can carry unlimited prose;
    code-fence budget bypass;
    nested/quoted detail authorization;
    HUSH divergence;
    stop/report divergence;
    status/report divergence;
    stale installed guards;
    reply-language/detail-mode coupling;
    large collection dumps;
    raw LOG/evidence duplication.

Fix adjacent defects only when evidence is concrete.

Do not embark on unrelated architectural rewrites.

======================================================================
PART Q — NON-GOALS
======================================================================

Do not:

    implement the future multi-worker pool;
    implement YAZADAYU;
    implement v9 resident runtime;
    redesign all SAIPEN UI;
    solve all strategic holds;
    publish a release;
    force external blockers green;
    weaken provenance honesty;
    suppress safety messages;
    hide real human blockers;
    remove evidence to obtain compactness;
    make all model_supplied ingress unusable without considering host capability;
    turn every short source into INVALID by string length;
    hard-code "test1";
    add an LLM semantic judge as the only authority boundary;
    infer operator authority from model confidence.

======================================================================
PART R — FINAL ACCEPTANCE
======================================================================

This target is DONE only when all applicable statements are true.

AUTHORITY

1. `model_supplied` remains distinguishable from trusted operator provenance.

2. Source persistence no longer silently grants operator authority.

3. Unwitnessed/model-supplied ingress cannot silently preempt active legitimate
   Work as `user_explicit`.

4. Unwitnessed ingress cannot silently pivot `/goal` as trusted human authority.

5. Exact SRC-164/T-1599 incident is RED before and GREEN after.

6. Exact SRC-146/T-1573 history has a regression preventing INVALID/NON_WORK
   from drifting through a fake implementation lifecycle.

7. T-1599 is canonically disposed without manual BOARD/STATE/LOG mutation.

8. T-1510 trajectory is restored coherently if still applicable.

RESPONSE

9. Runnable work defaults to silent continuation.

10. Normal DONE is compact.

11. `saipen stop` produces a compact handback, not a retrospective.

12. Human blocker output contains only decision/action-relevant information.

13. Large internal evidence does not linearly enlarge default chat.

14. Large blocker inventories are summarized by default.

15. Commit/evidence/test inventories are summarized by default.

16. Requested deep reports remain possible.

17. Requested handoffs/audits/specs remain possible as explicit artifacts.

18. A request for "summary" or "brief" does NOT authorize a larger detail
    budget.

19. Explicit deep-detail authorization works in supported ingress languages.

20. Model reasoning cannot authorize its own verbosity.

21. DETAILS is never available by default.

22. No code-fence or artifact-shaped bypass allows unsolicited novels.

23. Semantic facts are not redundantly repeated across response fields.

24. Default response size is approximately constant relative to internal
    evidence volume.

HOST ENFORCEMENT

25. OpenCode claims match actual installed behavior.

26. Claude claims match actual Stop/prompt capabilities.

27. Codex claims match actual Stop/trust/post-render limitations.

28. ZAICODE/ZCode remain honestly ADVISORY where no hook exists.

29. Intermediate suppression and final-response enforcement remain separate
    capabilities.

30. No post-render hook is described as pre-render prevention.

VALIDATION

31. Same-incident RED -> GREEN evidence exists.

32. Canonical validate is CURRENT_PASS.

33. Full declared core has red=0 and new_red=0.

34. No protocol state was manually falsified.

35. No unrelated publication occurred.

36. No unrelated Work was fabricated.

======================================================================
PART S — FINAL RESPONSE IS ITSELF AN ACCEPTANCE TEST
======================================================================

When all work is complete, DO NOT send the operator a novel describing how the
Anti-Roman system was implemented.

The final visible response for THIS task must itself demonstrate the result.

Unless a real human blocker remains, target approximately:

    STATUS
    DONE

    RESULT
    Anti-Roman + ingress-authority hardening complete; root incidents fixed.

    VALIDATION
    CURRENT_PASS | full core <N> | red 0 | new_red 0

    NEXT
    <one compact next fact or NONE>

Exact syntax must follow the final canonical response contract you actually
implement.

No implementation chronology.

No 54-row table.

No commit inventory.

No evidence dump.

Those facts belong in evidence.

======================================================================
CORE PRINCIPLES
======================================================================

MODEL TEXT IS NOT OPERATOR AUTHORITY.

CAPTURED BYTES ARE NOT AUTOMATICALLY TRUSTED INTENT.

PERSISTENCE IS NOT AUTHORIZATION.

THE MODEL MAY NOT AUTHORIZE ITS OWN VERBOSITY.

FULL MACHINE TRUTH DOES NOT REQUIRE FULL CHAT NARRATION.

EVIDENCE BELONGS IN EVIDENCE.

CHAT IS A CONTROL SURFACE.

IF WORK CAN CONTINUE:
    CONTINUE SILENTLY.

IF THE HUMAN MUST ACT:
    SAY ONLY WHAT THEY NEED.

IF WORK IS COMPLETE:
    REPORT THE RESULT.

IF THE HUMAN EXPLICITLY REQUESTS THE FULL STORY:
    THEN, AND ONLY THEN, GIVE THE BOUNDED FULL STORY.
