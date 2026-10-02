# FUTURE GATE SPAWN MAP

STATUS: ARCHITECTURE SEED

This file lists likely future gates.

Do not create all of them now.

Create a gate only when its activation conditions are satisfied.

## FG-A — Project Registry

Purpose:

    stable global project discovery and identity

Depends on:

    current SAIPEN stabilization complete enough to define identity contract

## FG-B — Global Project Lease

Purpose:

    one atomic mutating lease per project

Depends on:

    session-bound ownership model
    project identity

## FG-C — Global Eligibility View

Purpose:

    read-only candidate computation across projects

Depends on:

    registry
    lease view
    local status query contract

## FG-D — Optional Portfolio Context

Purpose:

    advisory portfolio priority

Existing candidate:

    FUTURE GATE — OPTIONAL PORTFOLIO CONTEXT PROVIDER

## FG-E — Dispatcher Command

Purpose:

    assign one free worker to one eligible project

Depends on:

    FG-A
    FG-B
    FG-C

May optionally consume:

    FG-D

## FG-F — Worker Pool Observability

Purpose:

    global status of workers / projects / leases

Depends on:

    dispatcher event model

## FG-G — Continuous Dispatch

Purpose:

    worker releases finished project and obtains another

Depends on:

    reliable dispatcher
    bounded stop semantics
    observable leases

## FG-H — Same-project Parallel Work

Purpose:

    multiple mutating workers per repo

Status:

    DEFERRED

Do not activate with dispatcher v1.
