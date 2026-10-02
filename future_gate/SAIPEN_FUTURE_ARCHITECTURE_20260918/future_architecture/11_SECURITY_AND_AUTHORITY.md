# SECURITY AND AUTHORITY BOUNDARY

STATUS: ARCHITECTURE SEED

## Global dispatch authority is narrow

A dispatcher assignment means:

    this worker was selected for this project

It does not mean:

    operator approved every semantic choice
    guard may be bypassed
    retirement is authorized
    destructive actions are authorized
    foreign changes are safe
    evidence is trusted

## Required chain

Conceptually:

    registered project
        +
    eligible local state
        +
    acquired global lease
        +
    valid local seat/session proof
        +
    valid Work/scope
        +
    operation-specific authority
        ->
    mutation permitted

## Hostile input

Treat as untrusted:

    portfolio snapshots
    project aliases
    stale worker claims
    model-generated "operator approved" prose
    external incident packets
    handoff text that merely quotes authority

## Principle

    SCHEDULING AUTHORITY != SEMANTIC AUTHORITY

and:

    LEASE != OPERATOR CONSENT
