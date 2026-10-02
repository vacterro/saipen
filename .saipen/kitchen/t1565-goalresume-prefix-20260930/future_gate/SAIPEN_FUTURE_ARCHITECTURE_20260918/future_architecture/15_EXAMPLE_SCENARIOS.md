# EXAMPLE SCENARIOS

STATUS: ARCHITECTURE SEED

## Scenario A — Two identical generic workers

Initial:

    SAIPEN      READY / free
    AUDAPACK    READY / free
    FastPrompter READY / free

Worker A:

    saipen dispatch

Result:

    lease SAIPEN -> A

Worker B at nearly same time:

    saipen dispatch

Result:

    SAIPEN lease conflict
    dispatcher retries candidate selection
    lease AUDAPACK -> B

Expected:

    no dual SAIPEN mutation

## Scenario B — Explicit busy project

Worker A owns AUDAPACK.

Worker B:

    saipen start AUDAPACK

Expected:

    explicit lease conflict

Forbidden:

    silently sending B to FastPrompter

## Scenario C — Portfolio provider absent

AUDAPACK Project Room not running.

Expected:

    local SAIPEN works
    registry works
    dispatcher uses fallback ordering
    no protocol failure

## Scenario D — High priority but blocked

Portfolio:

    SAIPEN MAIN0/1

Local:

    SAIPEN WAIT_OPERATOR

Expected:

    dispatcher does not fabricate work
    worker may be sent to next eligible project

SAIPEN remains pending operator input.

## Scenario E — Worker crashes

Worker A owns ProTrail and process disappears.

Expected:

    lease enters recoverable liveness path
    no immediate blind theft
    after proven stale/dead state, lease becomes reacquirable

## Scenario F — Continuous worker

Worker A:

    saipen dispatch --continuous

Flow:

    AUDAPACK slice DONE
    release AUDAPACK
    dispatch FastPrompter
    FastPrompter reaches WAIT_OPERATOR
    release/park according to safe policy
    dispatch ProTrail
    no routine confirmation prompt

## Scenario G — Twelve workers

Twelve generic workers start.

Fewer than twelve projects are eligible.

Expected:

    unique leases for eligible projects
    remaining workers IDLE
    no duplicate mutation ownership
    no speculative work generation
