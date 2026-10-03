SAIPEN

FUTURE GATE — MINIMUM NECESSARY IMPLEMENTATION / PONYTAIL-INSPIRED CORE DISCIPLINE

STATUS
FUTURE_ARCHITECTURE
KEEP_GATED
NOT AUTHORIZED FOR CURRENT RUNTIME IMPLEMENTATION

REFERENCE

External architecture reference:

    DietrichGebert/ponytail

Relevant inspected surfaces:

    AGENTS.md
    skills/ponytail/SKILL.md
    benchmarks/results/2026-06-18-agentic.md

Do NOT vendor Ponytail.

Do NOT install it as a hidden second authority.

Do NOT copy its prompt verbatim into SAIPEN Core.

Extract and evaluate the mechanism.

======================================================================
WHY THIS EXISTS
======================================================================

SAIPEN has become increasingly capable at:

    lifecycle enforcement
    recovery
    provenance
    verification
    authority
    host adaptation
    evidence preservation

That maturity also creates a new failure mode:

    protocol over-engineering.

Every defect can tempt the implementation to add:

    another abstraction
    another registry
    another owner
    another config layer
    another helper
    another state machine
    another compatibility path
    another fixture family
    another dependency

even when an existing canonical owner could absorb the change.

The future Core should explicitly resist unnecessary implementation growth.

The goal is NOT:

    write the fewest lines at any cost.

The goal is:

    implement the smallest complete mechanism that preserves all required
    correctness, authority, recovery, security and evidence invariants.

======================================================================
REFERENCE MECHANISM
======================================================================

Ponytail uses an ordered implementation ladder.

Adapt the CONCEPT, not the wording.

Before introducing new implementation machinery, ask in order:

    1. Does this mechanism need to exist at all?

    2. Does an existing SAIPEN canonical owner already solve it?

    3. Can an existing engine primitive be extended without duplicating truth?

    4. Does Python/OS/Git/native host behavior already provide the mechanism?

    5. Does an already-required dependency provide it safely?

    6. Can the defect be solved by one bounded predicate/transition/guard in
       the actual shared owner?

    7. Only then create a new mechanism.

Stop at the first rung that fully satisfies acceptance.

======================================================================
CORE PRINCIPLE
======================================================================

Candidate future invariant:

    MINIMUM NECESSARY MECHANISM

For every implementation change:

    understand the complete affected flow first;

    find the narrowest canonical owner;

    prefer deletion/reuse/extension over new parallel machinery;

    introduce no abstraction without a current demonstrated need;

    add no second source of truth;

    preserve all safety/evidence requirements;

    leave the smallest complete diff that fixes the root cause.

Shortest diff is NOT automatically correct.

The required ordering is:

    UNDERSTAND
        ->
    FIND ROOT OWNER
        ->
    MINIMIZE

never:

    MINIMIZE
        ->
    HOPE

======================================================================
ROOT-CAUSE RULE
======================================================================

A reported symptom is not necessarily the implementation owner.

Before patching one caller:

    identify all relevant callers / paths;

    identify the shared canonical owner;

    determine whether one repair there resolves the family.

Prefer:

    one correct shared guard

over:

    five symptom-specific guards

when they express the same invariant.

But do NOT force unrelated cases through one abstraction merely to reduce LOC.

======================================================================
SAIPEN-SPECIFIC LADDER
======================================================================

For any proposed new code, conceptually evaluate:

RUNG 1 — NO CHANGE

    Is current behavior already correct?

    Is the reported problem only stale evidence, configuration or caller misuse?

    Can the request be satisfied without protocol code?

RUNG 2 — EXISTING OWNER

    Does an existing canonical module already own this truth?

Examples:

    lifecycle
    ownership
    authority
    response_surface
    chat_style
    recovery
    source intake
    validation
    storage
    telemetry

If yes:

    repair there.

Do not create a sibling owner.

RUNG 3 — EXISTING PRIMITIVE

    Can an existing operation/predicate/classification be extended?

Prefer:

    one widened canonical predicate

over:

    a new parallel decision system.

RUNG 4 — NATIVE CAPABILITY

    Does Git, filesystem, Python stdlib, host hook, OS primitive or existing
    runtime contract already provide the required behavior?

Use it where its guarantees match acceptance.

Do not wrap a native primitive merely to rename it.

RUNG 5 — EXISTING DEPENDENCY

    Can an already-required dependency safely provide the mechanism?

Do not add a dependency for convenience alone.

RUNG 6 — MINIMAL NEW CODE

    Add the smallest new mechanism that owns the missing invariant.

RUNG 7 — NEW SUBSYSTEM

    Only when evidence proves the problem requires independent state,
    lifecycle or capability ownership.

New subsystem is the LAST option.

======================================================================
WHAT MUST NEVER BE MINIMIZED AWAY
======================================================================

This discipline must be explicitly subordinate to:

    protocol authority
    security boundaries
    trust-boundary validation
    data-loss prevention
    atomicity where required
    recovery correctness
    provenance
    canonical evidence
    lifecycle safety
    stale-worker protection
    capability honesty
    user-requested requirements
    required accessibility
    deterministic verification

A three-line implementation that loses one of these is larger in real cost than
a thirty-line correct implementation.

Do not optimize visible LOC while exporting complexity into undefined behavior.

======================================================================
NO SECOND AUTHORITY
======================================================================

Ponytail or any derived "minimalism" evaluator MUST NOT independently decide:

    ticket completion
    acceptance
    source disposition
    lifecycle phase
    ownership
    authority
    verification result
    safety approval
    publication permission

It may influence:

    implementation strategy

It may NOT redefine:

    protocol truth.

SAIPEN remains the sole authority.

======================================================================
ANTI-ABSTRACTION CHECK
======================================================================

Before adding any new:

    class
    registry
    adapter
    factory
    config field
    enum
    state file
    cache
    background service
    dependency
    compatibility layer

require one concrete answer:

    What current demonstrated requirement cannot be satisfied cleanly by the
    existing owner?

If there is no concrete answer:

    do not add it.

"May be useful later" is not acceptance evidence.

======================================================================
ANTI-DUPLICATION CHECK
======================================================================

Before implementing a new rule:

    search existing code and contracts for semantic equivalents.

Reject designs that create:

    two validators for one invariant;
    two authority classifiers;
    two lifecycle predicates;
    two response budget owners;
    two recovery paths for the same defect;
    adapter-local copies of canonical policy.

One invariant should have one canonical owner.

======================================================================
DELETION AS A VALID REPAIR
======================================================================

Protocol improvement may legitimately consist of:

    deleting dead code;
    deleting superseded compatibility;
    deleting duplicate tests after stronger equivalent coverage exists;
    deleting redundant state;
    deleting obsolete wrappers;
    collapsing parallel predicates into one owner.

Deletion must still preserve:

    historical evidence
    supported compatibility contracts
    required acceptance coverage

Do not preserve dead implementation merely because it already exists.

======================================================================
TEST DISCIPLINE
======================================================================

Do NOT adopt a naive rule such as:

    every branch needs a new test file.

Prefer the smallest test that proves the new behavior.

But SAIPEN differs from a normal product library:

    protocol invariants often require adversarial regression coverage.

Therefore test minimization must preserve:

    same-incident RED
    same-oracle GREEN
    relevant negative controls
    full-core new_red=0

Avoid duplicate tests that prove the exact same invariant at the exact same
boundary without adding failure coverage.

======================================================================
METRICS
======================================================================

Do not use LOC as the primary optimization target.

Candidate observational metrics:

    files touched
    lines added
    lines deleted
    new modules
    new state owners
    new dependencies
    new configuration fields
    duplicate predicates removed
    duplicate owners removed
    tests added
    tests removed as redundant
    full-core result
    regression escape count

The target is NOT:

    minimum LOC

The target is:

    minimum implementation complexity
    under unchanged correctness and safety.

======================================================================
CONDITIONAL EFFICIENCY RELATION
======================================================================

Future integration may expose an implementation-economy component to the
existing conditional efficiency telemetry.

It must remain observational.

It must NOT reward:

    fewer tests at the cost of confidence;
    removal of validation;
    skipped recovery;
    unsafe shortcuts;
    hidden complexity;
    moving logic into opaque prompts.

QUALITY remains independent and dominant.

======================================================================
BENCHMARK BEFORE CORE PROMOTION
======================================================================

Do not promote this discipline into SAIPEN Core solely because the external
project reports positive results.

Run a SAIPEN-specific controlled benchmark.

Select representative historical defects with known accepted solutions.

Include at minimum:

    small root-cause bug
    recovery bug
    authority bug
    lifecycle bug
    response-surface bug
    cross-host adapter bug
    state/provenance bug
    case where a genuinely new subsystem WAS necessary

Compare:

    BASELINE
        current SAIPEN implementation behavior

    MINIMUM-MECHANISM
        candidate discipline

Keep identical:

    task
    initial tree
    model/provider where possible
    acceptance
    validation suite

Measure:

    correctness
    new_red
    regression escape
    diff size
    files touched
    new abstractions
    execution time
    token use
    rework

A smaller diff that fails acceptance loses.

======================================================================
CRITICAL NEGATIVE CONTROL
======================================================================

Include cases where "minimal" is WRONG.

Examples:

    security validation
    atomic recovery
    generational lease protection
    provenance binding
    crash consistency

The candidate discipline must choose the larger correct mechanism where
necessary.

If it systematically prefers smaller unsafe code:

    REJECT.

======================================================================
PROMOTION GATE
======================================================================

DO NOT wait for BLOCKED count to reach zero.

BLOCKED includes legitimate:

    strategic holds
    publication authority
    capability boundaries
    external dependencies

Zero is not the maturity criterion.

Consider promotion only when:

    current P1 authority/intake defects are closed;

    current response-surface/anti-roman work is stable;

    continuation authority semantics are mechanically settled;

    no runnable P1 recovery deadlock remains;

    canonical validate is CURRENT_PASS;

    full core is repeatedly red=0 / new_red=0;

    long-run execution no longer exposes fundamental lifecycle corruption;

    SAIPEN-specific benchmark shows measurable benefit without quality loss.

Likely prerequisite owners at the current snapshot include at least:

    T-1600 / T-1601 family
        ingress provenance / false operator authority

    T-1494
        persistent vs bounded continuation authority

and any P1 successor created by the current response-surface work.

Do not bind promotion mechanically to these exact ticket numbers if later
history supersedes them.

Bind to the underlying capabilities.

======================================================================
ADOPTION LEVELS
======================================================================

Future rollout should be staged.

LEVEL 0 — RESEARCH

    external reference only

LEVEL 1 — REVIEW ADVISORY

    implementation review reports unnecessary machinery

    no mutation authority

LEVEL 2 — BUILD PLANNING CHECK

    before BUILD, candidate implementation is checked against the ladder

    advisory/refusal only where mechanically justified

LEVEL 3 — CORE DISCIPLINE

    canonical implementation planning requires proof that new machinery is
    necessary

Do not jump directly from external project to LEVEL 3.

======================================================================
PREFERRED FIRST ADOPTION
======================================================================

The safest first useful form is probably:

    REVIEW / AUDIT MODE

For an implementation diff, ask:

    what can be deleted?
    what duplicates an existing owner?
    what can reuse stdlib/native capability?
    what abstraction has only one current consumer?
    what code exists only "for later"?
    what rule is implemented in multiple places?

Produce a bounded deletion/simplification proposal.

Do NOT automatically mutate accepted code from this review alone.

This gathers SAIPEN-specific evidence before Core promotion.

======================================================================
RELATION TO ANTI-ROMAN WORK
======================================================================

Do not conflate:

    minimal implementation

with:

    terse human response.

Ponytail itself explicitly separates these concerns.

Its primary mechanism minimizes what the agent BUILDS.

SAIPEN's Response Surface / Anti-Roman work minimizes what the agent SAYS.

They are complementary but independent.

Desired future pair:

    RESPONSE SURFACE:
        minimum necessary human prose

    MINIMUM NECESSARY IMPLEMENTATION:
        minimum necessary code/mechanism

Both preserve correctness.

Neither may weaken evidence.

======================================================================
RELATION TO FUTURE WORKER POOL
======================================================================

A future worker router may eventually carry implementation-discipline
capabilities.

Example:

    worker supports minimum-mechanism planning

But this Future Gate must not depend on:

    persistent worker pool
    YAZADAYU
    resident runtime
    concurrency

It must remain usable with one worker/session.

======================================================================
RESEARCH OUTPUT
======================================================================

Before promotion produce:

    mechanism summary
    exact external revision
    SAIPEN overlap analysis
    benchmark results
    failure cases
    safety negative controls
    proposed canonical owner
    implementation surface
    migration cost
    rollback strategy
    final verdict

Verdict must be one of:

    ADAPT_CONCEPT
    REFERENCE_ONLY
    KEEP_GATED
    REJECT

Do not promote by enthusiasm.

======================================================================
CURRENT VERDICT
======================================================================

KEEP_GATED / HIGH-VALUE CANDIDATE

Reason:

    The mechanism directly addresses SAIPEN's growing risk of protocol
    over-engineering and duplicate machinery.

But:

    current authority/recovery/response stabilization remains higher priority.

Record now.

Benchmark later.

Promote only after the maturity gate above.

======================================================================
CORE IDEA
======================================================================

SAIPEN SHOULD NOT ONLY PREVENT AGENTS FROM DOING THE WRONG THING.

IT SHOULD ALSO PREVENT THEM FROM BUILDING FIVE THINGS
WHEN ONE EXISTING THING ALREADY SOLVES THE PROBLEM.

UNDERSTAND FIRST.

REUSE SECOND.

DELETE WHEN POSSIBLE.

BUILD ONLY WHAT IS NECESSARY.

NEVER MINIMIZE AWAY CORRECTNESS.