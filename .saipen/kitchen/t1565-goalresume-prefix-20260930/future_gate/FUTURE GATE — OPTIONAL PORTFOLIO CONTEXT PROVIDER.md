SAIPEN

FUTURE GATE — OPTIONAL PORTFOLIO CONTEXT PROVIDER

STATUS: REGISTERED / NOT IMPLEMENTED
DATE: 2026-09-18
OWNER DOMAIN: SAIPEN scheduler / external context boundary
PRIMARY PROVIDER CANDIDATE: AUDAPACK Project Room
PRIORITY: FUTURE RELEASE
CLASS: OPTIONAL ENRICHMENT / PORTFOLIO AWARENESS

======================================================================
1. PURPOSE
======================================================================

SAIPEN Core currently understands the truth of one project:

    STATE
    BOARD
    LOG
    intake
    lifecycle
    local next action

It does not know the operator's portfolio-level intent:

    which project currently deserves attention
    which project is parked
    which project may consume agent slots
    which project should wait even though local Work is READY

Future capability:

    OPTIONAL PORTFOLIO CONTEXT

The first provider may be AUDAPACK Project Room.

This MUST remain bonus context.

SAIPEN Core MUST remain fully functional when AUDAPACK or every other
portfolio provider is absent.

======================================================================
2. ARCHITECTURAL SEPARATION
======================================================================

Keep these concerns separate.

PROJECT TRUTH:

    owner:
        the project's own .saipen state

    answers:
        what exists
        what is blocked
        what is actionable
        what the local next action is

PORTFOLIO INTENT:

    owner:
        external human-controlled portfolio system

    first candidate:
        AUDAPACK Project Room

    answers:
        which projects currently deserve more or less attention

SCHEDULER DECISION:

    owner:
        scheduler / orchestrator

    answers:
        which legal local action should actually receive an agent slot now

HUMAN:

    may override portfolio intent and scheduler choice.

Critical invariant:

    PORTFOLIO PRIORITY != PROJECT STATE

External priority must never rewrite the project's canonical truth.

======================================================================
3. CORE MUST REMAIN STANDALONE
======================================================================

Required baseline:

    provider absent
        -> SAIPEN operates normally

    provider disconnected
        -> SAIPEN operates normally

    provider stale
        -> SAIPEN operates normally

    provider malformed
        -> SAIPEN ignores/rejects the optional context
        -> core lifecycle remains available

Forbidden:

    if AUDAPACK missing:
        refuse

    if project not MAIN0:
        stop

    if portfolio snapshot stale:
        block project lifecycle

Principle:

    FAIL OPEN FOR OPTIONAL CONTEXT
    FAIL CLOSED ONLY FOR SAIPEN'S OWN INVARIANTS

NONE is a normal integration state, not a protocol failure.

======================================================================
4. PROVIDER ABSTRACTION
======================================================================

Do NOT hard-wire SAIPEN Core to AUDAPACK.

Introduce an abstraction conceptually equivalent to:

    PortfolioContextProvider

Provider #1 may be:

    AUDAPACK Portfolio Provider

Future providers may include:

    another GUI
    SAICODE cockpit
    JSON/file source
    scheduler/orchestrator
    another operator-owned portfolio tool

SAIPEN should consume a provider contract, not parse AUDAPACK GUI state.

======================================================================
5. DATA FLOW
======================================================================

Preferred first version:

    AUDAPACK
        -> atomic read-only snapshot
        -> SAIPEN reads optional context

Direction:

    PROVIDER -> SAIPEN

SAIPEN Core does NOT move projects between portfolio lanes.

SAIPEN Core does NOT mutate AUDAPACK.

Human-controlled portfolio intent remains human-owned.

Future reverse flow may provide suggestions only.

Example:

    SAIPEN suggests:
        PROBLIP MAIN1 -> MAIN0
        reason: confirmed P0 regression

But no automatic lane mutation in the initial design.

======================================================================
6. MACHINE-READABLE SNAPSHOT
======================================================================

Example provider contract:

    {
      "schema_version": 1,
      "provider": "AUDAPACK",
      "generated_at": "2026-09-18T21:30:00+03:00",
      "projects": {
        "SAIPEN": {
          "lane": "MAIN0",
          "rank": 1,
          "attention": "active"
        },
        "SAIPAL": {
          "lane": "SIDE1",
          "rank": 1,
          "attention": "parked"
        }
      }
    }

This is illustrative, not frozen schema.

The provider should write atomically.

SAIPEN should treat the snapshot as external context, not canonical project
state.

======================================================================
7. PORTFOLIO LANES
======================================================================

AUDAPACK may continue exposing human-facing lanes such as:

    MAIN0
    MAIN1
    SIDE0
    SIDE1

Suggested operational meaning:

MAIN0:
    current primary investment
    highest attention
    preferred source of new agent work

MAIN1:
    active secondary projects
    regular work, but below MAIN0

SIDE0:
    maintenance / opportunistic
    work when explicitly useful or when higher lanes are quiet

SIDE1:
    parked usable product
    do not manufacture work
    wake only for explicit request, serious regression, dependency/security
    reason, or deliberate milestone

These names are presentation-level semantics.

SAIPEN should consume normalized policy rather than depend on lane names.

======================================================================
8. NORMALIZED ATTENTION POLICY
======================================================================

Possible normalized values:

    ACTIVE
    MAINTAIN
    PARKED
    FROZEN

AUDAPACK may map its human-facing lanes to these values.

Example:

    MAIN0 -> ACTIVE
    MAIN1 -> ACTIVE or MAINTAIN
    SIDE0 -> MAINTAIN
    SIDE1 -> PARKED

Exact mapping is provider policy and may evolve.

SAIPEN must not require the literal strings MAIN0 / SIDE1 for correctness.

======================================================================
9. LOCAL NEXT ACTION MUST REMAIN TRUE
======================================================================

Example local project truth:

    NEXT_ACTION:
        SCOUT T-126

External context:

    portfolio:
        lane: SIDE1
        attention: PARKED

SAIPEN must NOT rewrite the local truth to:

    HOLD

Preferred output:

    NEXT_ACTION:
        SCOUT T-126

    PORTFOLIO_HINT:
        SIDE1 / PARKED

    SCHEDULER_HINT:
        LOW_ATTENTION

Project truth remains truthful.

Portfolio context influences scheduling, not lifecycle semantics.

======================================================================
10. SCHEDULER USE
======================================================================

Portfolio context may be useful for:

    selecting the next project for a free agent slot

    ordering a global queue

    daily / weekly orientation

    deciding whether to continue automatically after a terminal milestone

    distributing concurrency across projects

Possible policy examples:

    MAIN0:
        several concurrent slots allowed

    MAIN1:
        lower concurrency

    SIDE0:
        opportunistic only

    SIDE1:
        zero automatic slots unless explicitly awakened

These are scheduler policies, not SAIPEN Core invariants.

Do not encode fixed slot counts in the first contract.

======================================================================
11. PRIORITY IS A TIE-BREAKER, NOT TRUTH
======================================================================

Portfolio priority must never override protocol truth.

Examples:

    MAIN0 project BLOCKED
        -> remains BLOCKED
        -> scheduler may choose another project

    SIDE1 project has confirmed P0/P1 regression
        -> SAIPEN must surface the defect
        -> scheduler may decide whether policy permits auto-wake

    READY project in MAIN1
        -> being READY does not mean it must receive the next agent slot

External priority helps answer:

    "Which legal work deserves the next unit of attention?"

It does not answer:

    "What is true inside this project?"

======================================================================
12. ORDER WITHIN A LANE
======================================================================

Provider may expose:

    lane
    rank

Example effective portfolio order:

    MAIN0 / 1
    MAIN0 / 2
    MAIN0 / 3

    MAIN1 / 1
    MAIN1 / 2

    SIDE0 / 1
    SIDE1 / 1

Do not add a complex multi-factor scoring system until measured use requires
one.

A later optional:

    priority_score

may be added without making it mandatory.

======================================================================
13. STALE / MISSING CONTEXT
======================================================================

Supported provider states should conceptually include:

    NONE
    OPTIONAL
    CONNECTED

Observed snapshot state may include:

    CURRENT
    STALE
    UNAVAILABLE
    INVALID

Example:

    portfolio:
        provider: AUDAPACK
        status: STALE
        age: 3d

Stale data may be shown informationally.

Schedulers should be free to ignore stale priority hints.

Missing/stale provider context MUST NOT mutate:

    BOARD
    STATE
    LOG
    local lifecycle

======================================================================
14. CACHING
======================================================================

Do not persist portfolio lane as canonical project state.

If caching is useful, keep it external/ephemeral.

Example:

    external_context:
        provider: AUDAPACK
        observed_lane: SIDE1
        observed_rank: 1
        observed_attention: PARKED
        observed_at: ...

If the provider disappears:

    portfolio_context: unavailable

No canonical lifecycle mutation follows.

======================================================================
15. SECURITY / AUTHORITY BOUNDARY
======================================================================

Portfolio context is advisory data.

It must NOT grant:

    mutation authority
    ticket ownership
    seat ownership
    retirement authority
    operator authority
    guard bypass

A malicious or corrupted provider snapshot must not be able to authorize
consequential SAIPEN operations.

Portfolio data may influence scheduling order only through an explicit
scheduler policy.

======================================================================
16. FAILURE BEHAVIOR
======================================================================

Provider read errors:

    -> informational warning at most
    -> no lifecycle refusal

Unknown schema version:

    -> ignore provider context
    -> report unsupported optional context
    -> continue Core

Malformed project record:

    -> reject that record or snapshot according to bounded provider contract
    -> do not poison Core

Unknown project:

    -> no local mutation

Provider disappears after previously being connected:

    -> context becomes unavailable/stale
    -> Core continues

======================================================================
17. NON-GOALS FOR INITIAL RELEASE
======================================================================

Do NOT initially build:

    two-way AUDAPACK control

    automatic lane movement

    automatic global priority rewriting

    mandatory portfolio daemon

    mandatory network service

    Core dependency on AUDAPACK

    portfolio data inside canonical BOARD/STATE

    portfolio-based guard authority

    complex score optimizer

    autonomous promotion/demotion of projects

    hard-coded MAIN0/MAIN1/SIDE0/SIDE1 logic inside Core

======================================================================
18. ACCEPTANCE
======================================================================

A future implementation is acceptable only if all of the following hold.

A. STANDALONE

    uninstall/remove provider
    -> SAIPEN full local lifecycle still works

B. OPTIONAL READ

    valid provider snapshot
    -> context visible

C. ZERO CANONICAL DRIFT

    reading/changing portfolio priority
    -> BOARD/STATE/LOG remain byte-identical

D. MISSING PROVIDER

    -> no BLOCKED
    -> no ERROR-level protocol failure

E. STALE PROVIDER

    -> marked stale/untrusted for scheduling
    -> Core continues

F. MALFORMED PROVIDER

    -> ignored/fail-open as optional context
    -> no authority granted

G. SCHEDULER ORDER

    two equally legal READY projects
    -> scheduler may prefer higher portfolio attention

H. LOCAL TRUTH

    lower-priority project retains truthful local next_action

I. SECURITY

    provider cannot grant seat/ticket/operator authority

J. NO CYCLE

    AUDAPACK may understand SAIPEN projects
    SAIPEN Core does not require AUDAPACK

======================================================================
19. TEST MATRIX
======================================================================

Future RED/GREEN controls should include:

1. no provider installed

2. provider connected with valid snapshot

3. provider disappears during runtime

4. stale snapshot

5. malformed JSON

6. unsupported schema version

7. project absent from provider

8. project present with ACTIVE

9. project present with PARKED

10. priority changes while project lifecycle remains byte-identical

11. provider attempts malformed/hostile authority-looking fields

12. scheduler uses priority only as advisory ordering

13. P0/P1 local defect surfaced even while portfolio says PARKED

14. provider failure never prevents status/start/recover/continue

15. AUDAPACK unavailable while SAIPEN tests remain fully green

======================================================================
20. FUTURE PRODUCT SURFACES
======================================================================

Potential UI/status exposure:

    saipen status

        Local next:
            SCOUT T-126

        Portfolio:
            provider: AUDAPACK
            lane: SIDE1
            attention: PARKED
            status: CURRENT

        Scheduler hint:
            LOW_ATTENTION

Potential global scheduler view:

    project
    local_state
    local_next
    portfolio_lane
    portfolio_rank
    attention
    provider_freshness

Do not let this presentation surface become a new canonical source of truth.

======================================================================
21. DESIGN PRINCIPLES
======================================================================

Core principles for this future gate:

    PROJECT TRUTH != PORTFOLIO INTENT

    PORTFOLIO INTENT != EXECUTION AUTHORITY

    LOCAL NEXT != GLOBAL NEXT

    OPTIONAL CONTEXT != DEPENDENCY

    STALE != FAILURE

    PROVIDER FAILURE != PROTOCOL FAILURE

    PRIORITY MAY ORDER WORK
    PRIORITY MUST NOT REWRITE TRUTH

    FAIL OPEN FOR OPTIONAL CONTEXT
    FAIL CLOSED FOR CORE INVARIANTS

    SAIPEN CORE MUST STAND ALONE

======================================================================
22. DELIVERY STRATEGY
======================================================================

Recommended staged implementation:

PHASE 1:
    provider-neutral read contract
    no scheduler behavior change

PHASE 2:
    AUDAPACK exports atomic snapshot
    SAIPEN displays external portfolio context

PHASE 3:
    scheduler consumes advisory attention/rank

PHASE 4:
    concurrency policies use portfolio hints

PHASE 5:
    optional SAIPEN suggestions back to the human/provider
    still no automatic portfolio mutation

Do not implement all phases in one wave.

======================================================================
23. FUTURE GATE EXIT CONDITION
======================================================================

This gate may become active implementation work only after:

    current SAIPEN stabilization/release corridor is green

    the global scheduler/queue owner is identified

    provider-neutral boundary is agreed

    AUDAPACK snapshot ownership is clear

    tests prove provider absence cannot block Core

Until then:

    REGISTERED
    NOT IMPLEMENTED
    NO CURRENT BLOCKER

======================================================================
END
======================================================================

Working name:

    Optional Portfolio Context

Alternate architecture name:

    External Priority Context Provider

One-line intent:

    Let SAIPEN know which projects currently deserve attention without making
    SAIPEN depend on the portfolio system that supplied that hint.
