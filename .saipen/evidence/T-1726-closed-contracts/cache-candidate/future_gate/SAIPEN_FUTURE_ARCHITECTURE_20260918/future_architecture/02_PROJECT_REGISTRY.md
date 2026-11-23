# PROJECT REGISTRY

STATUS: ARCHITECTURE SEED

## Purpose

Provide a stable project identity layer for global scheduling.

The registry answers:

    project_id -> project root
    project_id -> project lineage / identity
    project_id -> registration status
    project_id -> optional portfolio metadata source

It does not answer:

    what local ticket is active
    whether the project is healthy
    whether a worker may mutate it

## Required properties

Project registration must be:

- explicit or mechanically discoverable,
- lineage-aware,
- resistant to duplicate aliases,
- path-normalized,
- relocatable where possible,
- safe against stale roots.

## Candidate conceptual record

    {
      "project_id": "AUDAPACK",
      "root": "V:\\...\\AUDAPACK",
      "lineage": "...",
      "status": "AVAILABLE"
    }

Exact schema is deferred.

## Duplicate identity handling

Two paths claiming the same project identity must not both become mutable dispatcher targets.

Possible terminal classifications:

    SAME_PROJECT_ALIAS
    STALE_REGISTRATION
    PROJECT_ID_CONFLICT
    LINEAGE_CONFLICT

Conflict must fail closed for mutation.

## Availability

A registered project may be:

    AVAILABLE
    MISSING
    STALE
    CONFLICTING
    DISABLED

`MISSING` or `STALE` should not crash the dispatcher.

It should simply become ineligible.

## Important boundary

Registry truth is not project lifecycle truth.

A project can be:

    registry AVAILABLE
    local SAIPEN BLOCKED

and therefore not currently dispatchable.
