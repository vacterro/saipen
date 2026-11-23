# MULTI-PROJECT OBSERVABILITY

STATUS: ARCHITECTURE SEED

## Purpose

A global dispatcher without observability becomes an invisible slot machine.

The operator needs to see:

    worker
    assigned project
    project lease
    current local Work
    phase
    duration
    last meaningful action
    blocker
    portfolio lane/hint
    runtime/provider/model
    health
    release reason

## Example conceptual table

| Worker | Project | Local Work | Lease | Phase | Portfolio | State |
|---|---|---|---|---|---|---|
| A | SAIPEN | T-1401 | ACTIVE | BUILD | MAIN0/1 | WORKING |
| B | AUDAPACK | T-220 | ACTIVE | VERIFY | MAIN0/2 | WORKING |
| C | FastPrompter | T-98 | ACTIVE | SCOUT | MAIN0/3 | WORKING |
| D | - | - | NONE | - | - | IDLE |

## Required distinctions

Do not collapse:

    IDLE
    BLOCKED
    WAIT_OPERATOR
    INFRASTRUCTURE_UNMEASURED
    LEASE_CONFLICT
    CRASHED
    COMPLETED

These have different operational meanings.

## Event model

Future dispatcher events may include:

    WORKER_REGISTERED
    DISPATCH_REQUESTED
    PROJECT_SELECTED
    LEASE_ACQUIRED
    PROJECT_ENTERED
    LOCAL_STOP
    LEASE_RELEASED
    DISPATCH_RETRY
    WORKER_IDLE
    LEASE_RECOVERY

The exact event schema is deferred.

## Human control

Operator should be able to:

    inspect
    pause global dispatch
    disable a project
    prefer a project
    drain a worker
    release a stale lease through a proven recovery path

Do not require opening each OpenCode window to discover global state.
