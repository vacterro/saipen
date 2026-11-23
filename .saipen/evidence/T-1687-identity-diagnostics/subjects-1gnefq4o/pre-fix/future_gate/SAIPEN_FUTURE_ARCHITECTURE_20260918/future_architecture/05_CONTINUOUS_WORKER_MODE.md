# CONTINUOUS WORKER MODE

STATUS: ARCHITECTURE SEED

## Intent

Allow a generic worker to remain useful after one project slice completes.

Conceptual command:

    saipen dispatch --continuous

Behavior:

    acquire project lease
        ->
    execute legal local work
        ->
    stop at real local terminal
        ->
    release project lease
        ->
    request next eligible project
        ->
    repeat

## Real stop conditions

Continuous mode must stop or wait when:

    operator semantic decision is required
    safety stop is reached
    infrastructure failure prevents trustworthy progress
    no eligible projects exist
    global dispatcher is unavailable
    worker capability cannot satisfy remaining work

## Not a permission bypass

Continuous mode means:

    continue scheduling

It does not mean:

    force authority
    force destructive choice
    ignore project guards
    invent evidence
    steal active leases

Principle:

    FORCED SCHEDULING != FORCED AUTHORITY

## Relationship to local `cc all`

Local concept:

    continue this project until a real stopper

Global continuous concept:

    when this project slice ends, release it and dispatch another eligible project

These are different scopes and should remain separate commands/concepts.

## Idle behavior

If no project is eligible:

    worker becomes IDLE

It should not:

    create speculative tickets
    awaken PARKED projects without policy
    spin in a hot polling loop

A future orchestrator may use bounded wait/event-driven wakeup.
