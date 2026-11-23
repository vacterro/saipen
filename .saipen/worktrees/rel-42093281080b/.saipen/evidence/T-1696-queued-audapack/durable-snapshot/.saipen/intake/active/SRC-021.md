# T07 — MANAGED WORKER CAPACITY FOR UP TO SIX RUNS

Priority: P0
Depends on: T01, T06

## Current state

If zero workers exist, START AUDIT launches one dedicated Chromium worker.

That is sufficient for one run but not a transparent six-run workflow.

## Goal

Queue demand should automatically prepare enough dedicated CLEAN workers,
bounded by the existing hard maximum of six.

## Supervisor policy

For queued/active audit demand:

desired_managed_workers =
    min(6, max(1, queued_or_starting_run_count))

Do not necessarily launch six when only one audit exists.

## Worker lifecycle

- STARTING
- CLEAN
- BUSY/AUDITING
- OCCUPIED/COMPLETED
- OFFLINE

Only AUDAPACK-owned dedicated workers may be automatically:
- spawned;
- navigated;
- recycled.

Never manipulate random personal ChatGPT tabs.

## Spawn protection

Each planned worker slot needs:
- slot id
- generation
- launch cooldown
- heartbeat deadline

No repeated Popen on every status refresh.

## UI

Audit Runs summary can show:
`WORKERS 4/6 · CLEAN 1`

Details can show worker slots.

Normal user flow remains run-centric, not worker-centric.
