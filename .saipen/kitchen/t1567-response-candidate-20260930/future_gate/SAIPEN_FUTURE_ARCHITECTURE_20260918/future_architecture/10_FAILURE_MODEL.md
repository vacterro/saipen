# FAILURE MODEL

STATUS: ARCHITECTURE SEED

## Dispatcher unavailable

Per-project SAIPEN continues to operate locally.

Global dispatch is unavailable, not local lifecycle.

## Portfolio provider unavailable

Dispatcher falls back to deterministic non-portfolio ordering.

## Project registry stale

Affected project becomes ineligible until identity is re-established.

Other projects remain dispatchable.

## Lease broker unavailable

Fail closed for NEW global mutation leases.

Existing local project sessions may follow separately defined lease survival policy.

Do not guess ownership.

## Worker crash

Lease must become recoverable through bounded liveness semantics.

No immediate unsafe lease theft.

## Project disappears

Release/retire registry availability state.

Do not redirect the worker to a path that merely has the same folder name.

## Local SAIPEN says WAIT_OPERATOR

Dispatcher must not override the local semantic stop.

Possible worker behavior:

    release project lease if safe
    mark project waiting
    dispatch another eligible project

The waiting project remains pending until operator input arrives.

## No eligible projects

Worker becomes IDLE.

No speculative work generation.
