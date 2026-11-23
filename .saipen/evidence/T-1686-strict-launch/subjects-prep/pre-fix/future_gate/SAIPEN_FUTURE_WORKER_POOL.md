SAIPEN

FUTURE GATE — PERSISTENT MULTI-WORKER GOAL EXECUTION

TARGET FILE

future_gate/SAIPEN_FUTURE_WORKER_POOL.md

ROLE OF THIS DOCUMENT

Reference / future architecture only.

Do NOT:

- create implementation Work from this document now;
- enqueue tickets automatically;
- reorder the current stabilization BOARD;
- interrupt active SAIPEN work;
- claim any capability described here already exists.

Current STATE / BOARD / LOG / source receipts always outrank this future gate.

============================================================
VISION
============================================================

A SAIPEN `/goal` must belong to the durable WORK TRAJECTORY, not to one model,
one provider, one terminal, or one agent session.

Desired operator experience:

    configure available workers once
    -> start /goal
    -> leave the machine unattended
    -> workers may hit limits, context exhaustion, crashes or provider outages
    -> SAIPEN safely replaces them
    -> the SAME goal / ticket / phase continues
    -> operator returns to either:
         GOAL DONE
       or one real HUMAN-ONLY blocker

A worker is replaceable.

The work trajectory is persistent.

Core principle:

    WORKER IDENTITY MAY CHANGE.
    WORK IDENTITY MUST NOT.

============================================================
MOTIVATING EXAMPLE
============================================================

Operator configures a pool such as:

    Codex / strong model / high reasoning
    Claude / Opus-class model / strongest supported effort
    ZCode / GLM-class model / strongest supported effort
    Antigravity / configured strong model

Then starts:

    /goal finish stabilization

During unattended execution:

    Codex reaches provider/model limit
        -> durable checkpoint
        -> lease ends
        -> Claude takes over

    Claude reaches quota
        -> checkpoint
        -> lease ends
        -> another eligible worker takes over

    a weaker worker sees a ticket beyond its capability policy
        -> it does NOT blindly claim it
        -> router selects another qualified worker

The goal does not terminate merely because one worker terminates.

============================================================
1. WORKER DISCOVERY
============================================================

Future command family, naming subject to canonical CLI review:

    saipen workers discover
    saipen workers plan
    saipen workers apply
    saipen workers status

`workers discover` inspects locally available execution hosts/providers.

Examples:

    Codex CLI
    Claude Code
    ZCode
    Antigravity
    other registered SAIPEN-capable hosts

Discovery should determine only facts it can actually prove.

Possible properties:

    installed
    executable
    authenticated
    available models
    available reasoning/effort levels
    resume capability
    tool capability
    filesystem capability
    quota/headroom telemetry
    provider availability
    host adapter strength

Every discovered fact carries provenance.

Canonical confidence classes should distinguish at least:

    VERIFIED
    DECLARED_BY_OPERATOR
    INFERRED
    UNAVAILABLE

Do not claim subscription tier, model availability, effort support or quota state
merely because a CLI binary exists.

============================================================
2. WORKER REGISTRY
============================================================

After discovery, SAIPEN produces a proposed worker configuration.

The operator edits/reorders it once and approves it.

Conceptual configuration:

    version: 1

    policy:
      quality_first: true
      unattended_goal: true
      auto_failover: true

    workers:

      - id: codex-primary
        host: codex
        model: <verified/configured>
        effort: high
        preference: 100
        capabilities:
          - architecture
          - implementation
          - recovery
          - review

      - id: claude-strong
        host: claude
        model: <verified/configured>
        effort: <strongest-supported>
        preference: 95

      - id: zcode-glm
        host: zcode
        model: <verified/configured>
        effort: <supported>
        preference: 75

      - id: antigravity
        host: antigravity
        model: <configured>
        effort: <supported>
        preference: 70

Exact schema must be designed later.

The important contract is:

    operator configures the pool;
    SAIPEN owns deterministic selection from that pool.

Adapters do not maintain independent routing policy.

============================================================
3. DISCOVERY -> PLAN -> APPROVAL UX
============================================================

Desired first-run flow:

    saipen workers discover

SAIPEN reports actual capabilities.

Then:

    saipen workers plan

SAIPEN generates a recommended template using:

    QUALITY > TIME
    actual host capabilities
    actual available models
    supported reasoning/effort controls
    resume ability
    quota/headroom telemetry when available

Operator may edit:

    ordering
    enabled workers
    allowed models
    effort
    role/capability restrictions
    cost policy
    provider preferences

Then:

    saipen workers apply

SAIPEN displays the exact proposed effective policy.

Example operator view:

    PRIMARY
    Codex / <model> / High

    FAILOVER 1
    Claude / <model> / strongest supported

    FAILOVER 2
    ZCode / GLM / strongest supported

    FAILOVER 3
    Antigravity / <model>

    GOAL SURVIVES WORKER EXIT: YES
    AUTO FAILOVER: YES
    APPROVAL PER HANDOFF: NO

Operator approves once.

No repeated human confirmation is required for ordinary failover afterward unless
a later operation independently requires operator authority.

============================================================
4. ELIGIBILITY FIRST, PREFERENCE SECOND
============================================================

Do NOT implement failover as only:

    worker 1 unavailable
    -> worker 2
    -> worker 3

Selection must first determine which workers are CAPABLE of the current Work.

Conceptual selection:

    ticket requirements
        INTERSECT
    worker capabilities
        INTERSECT
    current availability

Then apply preference among eligible workers.

Example:

A P1 protocol/recovery architecture ticket may require:

    reasoning >= HIGH
    recovery capability
    full filesystem tools
    long-context suitability

A weaker worker must not receive that Work solely because it is the next item in
the fallback list.

But the same worker may be suitable for:

    fixture updates
    mechanical tests
    lint repairs
    documentation synchronization
    bounded maintenance

============================================================
5. ROUTING PRIORITY
============================================================

Default philosophy:

    QUALITY > TIME

A future router should prefer approximately:

    1. required capability
    2. task suitability
    3. evidence / resume fidelity
    4. expected quality class
    5. current availability / headroom
    6. cost
    7. speed

Do not optimize cost or speed ahead of correctness.

The conditional EFFICIENCY KPI must never become a routing objective that causes
quality degradation.

Metrics observe.

Metrics do not govern correctness.

============================================================
6. WORKER STATUS / HEADROOM
============================================================

Workers should expose a bounded runtime state where available:

    READY
    BUSY
    LOW_HEADROOM
    CONTEXT_NEAR_LIMIT
    RATE_LIMITED
    MODEL_LIMIT
    AUTH_REQUIRED
    PROVIDER_UNAVAILABLE
    HOST_FAILED
    DISABLED

Provider-specific details remain adapter-owned evidence.

The canonical worker registry consumes normalized facts.

If quota/headroom is available, SAIPEN may perform PLANNED HANDOFF before a hard
failure.

Example:

    worker has 2% usable headroom
    current bounded slice can safely finish
    next BUILD is large

Preferred behavior:

    finish current safe boundary
    -> checkpoint
    -> hand off before failure

rather than:

    start large Work
    -> die mid-edit

============================================================
7. EXECUTION LEASE
============================================================

A durable goal needs one canonical execution lease.

Conceptual state:

    GOAL G-42
    WORK T-1579
    PHASE BUILD

    LEASE
      worker: codex-primary
      session: abc123
      generation: 17
      acquired_at: ...
      heartbeat: ...
      expires_at: ...

The lease defines who currently has mutation authority.

Only the current generation may perform owned mutations.

============================================================
8. GENERATIONAL WORKERS
============================================================

Every worker handoff increments a generation.

Example:

    generation 17 -> Codex
    generation 18 -> Claude

If the old Codex process wakes after failover:

    its generation != current generation

Therefore mutation is refused.

This prevents two workers from simultaneously continuing the same Work after a
late recovery.

A stale worker may be allowed read-only diagnostics where safe, but never active
mutation authority.

============================================================
9. FAILOVER TRIGGERS
============================================================

Worker replacement may occur after evidence such as:

    MODEL_LIMIT
    RATE_LIMIT
    CONTEXT_EXHAUSTED
    HOST_EXIT
    HOST_CRASH
    PROVIDER_UNAVAILABLE
    AUTH_EXPIRED
    planned LOW_HEADROOM handoff
    operator-requested worker replacement

These are WORKER terminal conditions.

They are NOT GOAL terminal conditions.

============================================================
10. GOAL TERMINAL CONDITIONS
============================================================

For an unbounded `/goal`, the trajectory stops only when one canonical terminal
condition holds.

Examples:

    GOAL COMPLETE

    REAL HUMAN-ONLY BLOCKER

    REQUIRED OPERATOR / SAFETY AUTHORITY

    EXPLICIT OPERATOR PAUSE

    EXPLICIT OPERATOR CANCEL

These must NOT terminate the goal:

    ticket completed
    phase completed
    context window exhausted
    model quota reached
    worker crashed
    host restarted
    provider temporarily unavailable
    current model session ended

============================================================
11. BOUNDED GOALS
============================================================

Support explicit finite authority independently from worker lifetime.

Examples:

    complete exactly 2 eligible tickets

    continue until T-100 is DONE

    execute through VERIFY

    work until the next human-only boundary

A bounded goal survives worker replacement exactly like an ordinary goal.

But once its explicit bound is satisfied:

    STOP

Example:

    operator: close 2 tickets

    worker A closes ticket 1
    worker A dies

    worker B closes ticket 2

    goal terminates

Worker B must NOT start ticket 3.

This distinguishes:

    execution persistence

from:

    execution authority.

============================================================
12. PERSISTENT SUPERVISOR
============================================================

The component responsible for replacing workers must outlive the worker.

Do not place worker-replacement responsibility only inside:

    Codex
    Claude
    ZCode
    another disposable model session

because the mechanism would die with the worker it needs to replace.

A persistent supervisor must own process orchestration.

Possible future forms:

    saipen supervisor

or integration with a dedicated orchestration layer such as:

    SAIRELAY
    ZAICODE runtime
    another durable local service

Architectural separation:

    SAIPEN
        owns protocol state, policy, Work, leases, routing truth and handoff
        evidence.

    SUPERVISOR
        physically starts/stops/resumes worker processes.

Do not prematurely force process-manager implementation into the core protocol if
a cleaner external supervisor boundary exists.

============================================================
13. HANDOFF IS NOT CHAT TRANSFER
============================================================

Correctness must not depend on copying the previous model's conversation.

A replacement worker receives canonical minimal context.

At minimum:

    goal identity
    ticket
    phase
    current lease generation
    exact source/acceptance
    current owner
    owned diff
    latest verified evidence
    known blocker state
    current protocol/style authorities
    canonical next action

Native provider session resume may be used as an optimization.

It must not be required for correctness.

The durable source of truth is SAIPEN state/evidence, not the previous model's
memory of the conversation.

============================================================
14. SAFE HANDOFF SEQUENCE
============================================================

Conceptual failover:

    current worker
        -> durable checkpoint if possible

    supervisor
        -> marks worker exit / limit reason

    SAIPEN
        -> verifies current work state
        -> closes/releases/expires old lease
        -> selects eligible replacement
        -> increments generation

    supervisor
        -> launches replacement host/model/effort

    replacement
        -> loads protocol authorities
        -> admission / capability checks
        -> acquires current lease
        -> saipen continue

    SAME GOAL CONTINUES

If the old worker died before checkpoint:

    canonical recovery owns reconstruction.

Do not trust a partial prose handoff from the dying model.

============================================================
15. MODEL / EFFORT POLICY
============================================================

Worker configuration must allow explicit:

    host
    provider
    model
    reasoning/effort level

where the host actually supports them.

Never invent unsupported effort controls.

Each setting carries capability provenance.

Possible classifications:

    VERIFIED_SUPPORTED
    OPERATOR_DECLARED
    UNAVAILABLE

If a configured model disappears:

    route according to policy

rather than silently selecting an arbitrary replacement model.

============================================================
16. FAIL-OPEN PHILOSOPHY
============================================================

Prefer degraded useful operation over unnecessary total stoppage.

If preferred worker unavailable:

    choose another eligible worker.

If strongest model unavailable but a lower-capability worker safely satisfies the
current ticket requirements:

    continue.

Hard-block only when:

    no available worker satisfies the minimum capability contract

or:

    continuing would be unsafe / unauthorised.

============================================================
17. SECURITY / BLAST RADIUS
============================================================

Worker orchestration must preserve existing SAIPEN safety properties.

Replacement workers must not gain broader authority merely because failover
occurred.

Preserve:

    ownership
    protected protocol state
    tree-under-test protection
    lifecycle gates
    verification gates
    response enforcement
    recovery evidence
    no-publish authority
    source coverage

Worker selection never overrides protocol authority.

============================================================
18. LONG-RUN TARGET
============================================================

Future acceptance should include a real long-run carrier.

Example:

    start `/goal`
    deliberately terminate workers repeatedly
    force model/provider limits
    restart hosts
    replace models/providers
    recover from stale sessions

Require:

    same goal identity survives
    same Work trajectory survives
    no duplicate active writer
    stale generations cannot mutate
    no manual Continue
    no lost acceptance
    no fabricated DONE
    final validation green

This naturally extends the existing 24H autonomous-soak direction.

============================================================
19. OPERATOR SURFACE
============================================================

Future useful commands may include:

    saipen workers discover
    saipen workers plan
    saipen workers apply
    saipen workers status

    saipen workers enable <id>
    saipen workers disable <id>

    saipen goal workers
    saipen goal handoff
    saipen supervisor status

Exact CLI is not fixed by this future document.

Prefer a small coherent command family over accumulating one-off switches.

============================================================
20. OBSERVABILITY
============================================================

Operator should be able to see compactly:

    active goal
    current ticket/phase
    current worker
    current model
    current effort
    lease generation
    worker headroom
    last handoff reason
    handoff count
    available fallback workers

Example future final report:

    STATUS
    GOAL DONE

    RESULT
    Stabilization completed across 4 worker sessions.

    VALIDATION
    CURRENT_PASS | core new_red=0

    EFFICIENCY
    ~87% MED | progress 92 | rework 81 | autonomy 96 | human 100

    WORKERS
    4 workers | 5 handoffs | 0 human interventions

No intermediate prose spam is required.

============================================================
21. YAZADAYU FUTURE RELATION
============================================================

Do NOT couple this Future Gate to YAZADAYU implementation now.

However this subsystem is a natural future substrate for a persistent entity such
as YAZADAYU.

Possible later architecture:

    YAZADAYU
        owns durable high-level continuity / identity / direction

    SAIPEN
        owns safe durable work trajectories

    worker pool
        supplies replaceable computational workers

Therefore YAZADAYU would not need to be identical to one provider model.

The entity may persist while its underlying computational workers change.

This is future integration context only, not current scope.

============================================================
22. CORE DESIGN PRINCIPLE
============================================================

The system must evolve from:

    autonomous agent

to:

    autonomous execution trajectory

The desired invariant is:

    WORKER MAY DIE.
    WORK MUST SURVIVE.

And for bounded authority:

    WORK MUST SURVIVE WORKER DEATH.
    WORK MUST NOT SURVIVE ITS AUTHORIZED BOUND.

============================================================
FUTURE ACCEPTANCE BAR
============================================================

Do not promote this gate to implementation until prerequisites are sufficiently
mature.

Likely prerequisites include:

    stable worker/session identity
    durable execution lease semantics
    reliable recovery
    unattended continuation
    bounded goal authority
    host capability registry
    24H field evidence
    concurrency safety
    protected mutation boundaries

When eventually implemented, acceptance should require:

1. Worker discovery is evidence-based.
2. Operator can approve/edit a generated worker plan.
3. Models and efforts are explicit where supported.
4. Routing is eligibility-first.
5. `/goal` survives model/provider/session death.
6. Worker replacement requires no ordinary human Continue.
7. Stale workers cannot mutate after handoff.
8. Work/ticket identity remains stable across workers.
9. Native conversation resume is optional, not authoritative.
10. A persistent supervisor outlives individual workers.
11. Bounded goals stop exactly at their authorized boundary.
12. Unbounded goals stop only at canonical goal terminal conditions.
13. Quality remains higher priority than speed/cost.
14. Fail-open degradation works where safe.
15. Full protocol safety gates survive worker replacement.
16. Long-run forced-failure testing proves repeated handoff.
17. Final operator reporting includes worker/handoff evidence.
18. No provider/model-specific policy is duplicated outside the canonical worker
    registry/router.

Keep this document as FUTURE GATE / reference architecture until explicitly
promoted through normal SAIPEN source intake.