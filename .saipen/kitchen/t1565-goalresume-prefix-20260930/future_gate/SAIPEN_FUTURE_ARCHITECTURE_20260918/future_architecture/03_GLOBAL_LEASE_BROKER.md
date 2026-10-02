# GLOBAL LEASE BROKER

STATUS: ARCHITECTURE SEED

## Purpose

Prevent two generic workers from accidentally mutating the same project at the same time.

## Initial invariant

    ONE LIVE MUTATING LEASE PER PROJECT

This is intentionally more conservative than future ticket-level parallelism.

## Lease identity

A future lease should be bound to enough identity to reject stale reuse.

Conceptually:

    lease_id
    project_id
    project_lineage
    worker/session identity
    runtime generation
    acquired_at
    renewed_at
    expiry / liveness policy

Exact fields are deferred.

## Atomic acquisition

Required conceptual primitive:

    TRY_ACQUIRE(project, worker)

Possible results:

    ACQUIRED
    ALREADY_OWNED_BY_THIS_WORKER
    LEASE_CONFLICT
    PROJECT_INELIGIBLE
    STALE_REGISTRATION

The acquisition decision and persisted lease state must not race.

## Release

A lease may release on:

    terminal work slice
    clean worker exit
    explicit release
    verified stale/dead worker recovery

A worker must not retain mutation authority forever because its process crashed.

## Recovery

Lease recovery must distinguish:

    genuinely live owner
    crashed owner
    unreachable but still potentially live owner
    stale generation
    replaced project lineage

Do not steal a lease merely because a heartbeat was delayed once.

## Authority boundary

Global lease means:

    this worker may attempt project work

It does NOT itself grant:

    operator semantic authority
    ticket retirement authority
    guard bypass
    source closure authority

Local SAIPEN still validates the actual operation.

## Future extension

Ticket/scope leases inside one project are deferred to:

    07_MULTI_WORK_PER_PROJECT_DEFERRED.md
