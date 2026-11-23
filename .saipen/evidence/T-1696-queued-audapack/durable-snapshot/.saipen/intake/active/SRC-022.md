# T08 — OPTIONAL BATCH START FOR UP TO SIX PROJECTS

Priority: P1
Depends on: T01-T07

## Why

Once single-project START is proven reliable, make the six-run workflow convenient.

Add a secondary explicit action:
`START GROUP`
or:
`START SELECTED`

Do not replace the normal `START AUDIT`.

## Scope

Queue up to six enabled projects from:
- selected group;
- or explicit multi-selection if Project Room supports it cleanly.

Before start show a compact confirmation:
- project names
- profile
- count

## Behavior

Each project receives an independent Audit Run.
One failure must not cancel the other five.

Example:
- 5 queue successfully
- 1 pack fails
Result:
- 5 continue
- 1 lane shows FAILED · Pack failed

## No fake parallelism

The queue may contain more than current CLEAN workers.
Workers are prepared/claimed as capacity becomes available.

## Tests

- six projects -> six independent runs.
- seventh request stays queued or is explicitly refused by the chosen batch policy, never silently dropped.
- one project already active -> reuse/skip, no duplicate.
