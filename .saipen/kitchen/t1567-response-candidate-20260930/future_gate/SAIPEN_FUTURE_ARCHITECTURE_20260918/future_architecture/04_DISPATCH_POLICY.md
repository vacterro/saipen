# DISPATCH POLICY

STATUS: ARCHITECTURE SEED

## Purpose

Define how a free worker chooses among several legal projects.

## Inputs

Possible inputs:

    local project actionability
    project lease availability
    explicit operator request
    portfolio attention
    portfolio rank
    ticket severity
    queue age
    dependency readiness
    worker capability constraints
    provider/model compatibility

Not all inputs belong in version 1.

## Priority hierarchy

First principle:

    EXPLICIT TARGET > GENERIC DISPATCH POLICY

If operator says:

    saipen start AUDAPACK

the dispatcher must not silently switch to another project.

For generic dispatch:

    filter illegal/ineligible projects first
    rank only among legal candidates

Do not rank first and then discover the winner cannot execute.

## Optional portfolio context

Portfolio data may affect order.

Example:

    MAIN0 / rank 1
    MAIN0 / rank 2
    MAIN1 / rank 1
    SIDE0 / rank 1
    SIDE1 / parked

But if portfolio context is absent:

    dispatcher still works

Fallback policy must be deterministic.

Possible fallback inputs:

    explicit global queue
    severity
    readiness
    age
    stable project_id order

Exact fallback policy should become a separate FUTURE GATE.

## No fake activity

If the highest-priority project is BLOCKED:

    do not create synthetic Work merely to keep it busy

Try the next eligible project.

## No priority-as-authority

A high priority never bypasses:

    ownership
    guard
    recovery
    source truth
    operator decision
