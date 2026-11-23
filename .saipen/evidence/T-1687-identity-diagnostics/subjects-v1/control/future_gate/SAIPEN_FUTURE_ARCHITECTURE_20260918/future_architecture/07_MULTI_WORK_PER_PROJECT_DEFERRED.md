# MULTI-WORK PER PROJECT — DEFERRED ARCHITECTURE

STATUS: DEFERRED ARCHITECTURE  
IMPLEMENTATION: DO NOT START WITH DISPATCHER V1

## Idea

Future SAIPEN may allow multiple mutating workers inside one repository if their scopes provably do not conflict.

Concept:

    one project
        -> multiple Work leases

Possible condition:

    scope(T-A) ∩ scope(T-B) = empty

## Why deferred

Repository concurrency is not only file overlap.

Shared risk surfaces include:

    git index
    generated files
    lockfiles
    migrations
    test fixtures
    runtime generation
    package metadata
    canonical STATE / BOARD / LOG
    shared caches
    build artifacts
    install/injection outputs

Two tickets can touch disjoint source files and still conflict operationally.

## Version 1 rule

    ONE LIVE MUTATING LEASE PER PROJECT

Keep this rule until the dispatcher is field-proven.

## Future prerequisite

Before multiple mutating workers per project, SAIPEN would need an explicit model for:

    work scope
    shared surfaces
    write-set declaration
    dynamic overlap
    canonical state serialization
    git commit/index coordination
    generated artifact ownership
    integration/merge gates

This is a separate architecture branch and should spawn its own future gates.
