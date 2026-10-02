# FUTURE ARCHITECTURE ROADMAP

STATUS: PLANNING ONLY  
DO NOT IMPLEMENT AS ONE WAVE

## Stage 0 — Preserve architecture

Goal:

    keep the design visible without affecting current work

Deliverables:

    this directory
    architecture index
    explicit relation to future gates

Exit:

    no implementation side effects

## Stage 1 — Project Registry FUTURE GATE

Goal:

    stable project_id -> root / lineage discovery

Acceptance themes:

    duplicate detection
    stale path handling
    deterministic identity
    read-only global listing

Do not add dispatch yet.

## Stage 2 — Global Lease Broker FUTURE GATE

Goal:

    one live mutating lease per project

Acceptance themes:

    atomic acquisition
    stale-owner recovery
    no lease theft
    session/generation binding

Do not add portfolio priority yet.

## Stage 3 — Read-only Global Eligibility FUTURE GATE

Goal:

    compute which registered projects are legally dispatchable

Inputs:

    registry
    local SAIPEN state
    lease availability

Output:

    deterministic eligible candidate set

No worker assignment yet.

## Stage 4 — Optional Portfolio Context integration

Goal:

    consume advisory priority where available

Expected related gate:

    OPTIONAL PORTFOLIO CONTEXT PROVIDER

Must remain optional.

## Stage 5 — `saipen dispatch` FUTURE GATE

Goal:

    generic worker receives one eligible project

Acceptance:

    explicit project targeting never substitutes
    generic dispatch skips leased/ineligible projects
    atomic selection + lease
    deterministic fallback without portfolio provider

## Stage 6 — Multi-project observability FUTURE GATE

Goal:

    operator sees workers, leases, projects, blockers and idle capacity

No hidden worker pool.

## Stage 7 — Continuous Worker FUTURE GATE

Goal:

    release completed project slice and dispatch next

Acceptance:

    no "continue?" babysitting
    bounded idle behavior
    real operator decisions remain real stops
    no forced authority

## Stage 8 — Field polygon

Use several generic workers.

Prove:

    duplicate dispatch race
    worker crash
    project disappearance
    provider disappearance
    WAIT_OPERATOR handoff
    all projects blocked
    mixed MAIN0/MAIN1/SIDE policies
    no wrong-repo mutation
    no duplicate mutation lease

## Stage 9 — Only after proven

Consider:

    multiple mutating Work leases inside one project

This is NOT part of dispatcher v1.
