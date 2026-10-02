# ADOPTION RULES

STATUS: ARCHITECTURE GOVERNANCE

## Why this file exists

Architecture seeds should not become accidental implementation authority.

## Rule 1

Do not convert this directory directly into active Source/Work.

## Rule 2

When implementation becomes timely, choose ONE bounded slice and create ONE FUTURE GATE.

Example:

    architecture seed:
        Global Project Dispatcher

first bounded gate:
        Project Registry

not:

        "implement dispatcher architecture"

## Rule 3

Each FUTURE GATE must define:

    owner
    scope
    non-goals
    activation prerequisites
    RED controls
    GREEN acceptance
    migration behavior
    failure behavior
    rollback/disable behavior where relevant

## Rule 4

Architecture documents may be revised as evidence improves.

Do not rewrite past canonical project history to make old architecture notes look prescient.

## Rule 5

A future gate derived from this architecture should link back to:

    future_architecture/README.md
    future_architecture/00_ARCHITECTURE_MAP.md

and the specific owner document.

## Rule 6

If a later design contradicts this seed:

    record the decision
    update the architecture seed
    do not silently implement the contradiction

## Rule 7

The first implementation must remain narrow.

Preferred sequence:

    registry
    lease broker
    eligibility
    optional portfolio hints
    one-shot dispatch
    observability
    continuous dispatch
    field polygon

Only then consider same-project parallel mutation.
