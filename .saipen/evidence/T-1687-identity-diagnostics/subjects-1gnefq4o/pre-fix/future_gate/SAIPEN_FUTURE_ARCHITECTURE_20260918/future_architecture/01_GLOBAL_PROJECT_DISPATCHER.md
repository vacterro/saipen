# GLOBAL PROJECT DISPATCHER

STATUS: ARCHITECTURE SEED  
IMPLEMENTATION: NOT STARTED

## Intent

Turn generic agent sessions into a worker pool.

Today an operator often mentally assigns:

    OpenCode window 1 -> SAIPEN
    OpenCode window 2 -> AUDAPACK
    OpenCode window 3 -> FastPrompter

Future target:

    OpenCode window 1 -> saipen dispatch
    OpenCode window 2 -> saipen dispatch
    OpenCode window 3 -> saipen dispatch

The dispatcher assigns each free worker the highest-priority legal project that is not already leased.

## Explicit vs implicit selection

Explicit project command:

    saipen start AUDAPACK

Semantics:

    target AUDAPACK only

If AUDAPACK is already leased:

    return a truthful conflict

Forbidden:

    silently substitute FastPrompter or another project

Generic dispatch command:

    saipen dispatch

Semantics:

    choose the best eligible free project according to scheduler policy

Possible constrained form:

    saipen dispatch --pool MAIN0

Possible future continuous form:

    saipen dispatch --continuous

## Example

Portfolio ordering:

    1. SAIPEN
    2. AUDAPACK
    3. FastPrompter
    4. ProTrail

Worker A:

    saipen dispatch

Result:

    SAIPEN leased to Worker A

Worker B starts simultaneously:

    saipen dispatch

It observes SAIPEN as leased and atomically claims:

    AUDAPACK

Worker C then receives:

    FastPrompter

## Non-negotiable property

Selection and lease acquisition must behave atomically.

Forbidden race:

    A sees SAIPEN free
    B sees SAIPEN free
    A claims
    B claims

Required behavior:

    TRY_ACQUIRE(project, worker, generation)

Exactly one succeeds.

The loser retries scheduling against the next eligible candidate.

## Local truth remains local

The dispatcher must not decide:

    which ticket is DONE
    whether evidence is valid
    whether a recovery route is legal
    whether operator authority exists

Those remain per-project SAIPEN responsibilities.

## Initial project-level concurrency

Version 1 rule:

    ONE LIVE MUTATING LEASE PER PROJECT

Read-only observation may be separately allowed.

Do not implement multi-ticket concurrent mutation in the first dispatcher release.
