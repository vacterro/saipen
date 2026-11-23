# T14 — REAL WINDOWS RELEASE GATE: SIX RUNS

Priority: RELEASE GATE
Depends on: T01-T13 as implemented

Do not close this from unit tests alone.

## A — one click, zero workers

1. Close dedicated workers.
2. Select project.
3. Click START AUDIT once.

Expected:
- PREPARING
- dedicated worker starts automatically
- job queues
- worker becomes CLEAN
- run proceeds
- no second click.

## B — exact visible stages

Observe:
PREPARING
-> WAITING/ATTACHING
-> STARTING
-> AUDIT 0/N
-> AUDIT 1/N
-> ...
-> SAVING
-> AUDIT READY

No state should remain falsely stale for ten seconds when generation events are flowing.

## C — six projects

Queue six projects.

Expected:
- six run lanes;
- no more than six managed workers;
- each run independent;
- eventually six lanes can visibly show `AUDIT READY ✓`.

## D — busy capacity

All six workers busy.
Queue another run if queue policy allows.

Expected:
`WAITING FOR WORKER`
not failure.

## E — pack failure

One project cannot pack.

Expected:
its run FAILED with a clear reason;
other runs unaffected.

## F — attachment retry

Transient attachment delay.

Expected:
bounded retry or wait;
no duplicate Core;
UI shows RETRYING only if relevant.

## G — cancel pre-start

Cancel before START boundary.

Expected:
CANCELLED;
no Core;
lane terminal.

## H — post-start worker loss

Lose worker after START.

Expected:
BLOCKED / RECOVERY;
no automatic duplicate Core;
no misleading READY.

## I — result truth

Artificially delay final_handoff persistence after final browser response.

Expected:
SAVING
until durable proof exists.

Only then:
AUDIT READY.

## J — application restart

Restart AUDAPACK during:
- PREPARING
- WAITING
- AUDITING
- READY

Expected:
correct run reconstruction;
no duplicate dispatch;
no duplicate notifications.

## K — no console spam

Run six audits for an extended period.

Expected:
- no CMD/PowerShell flashing;
- no poll hammer;
- no worker launch storm;
- no repeated second-click instructions.

## Final product proof

The user can:
- press START AUDIT once;
- walk away;
- later return and see `AUDIT READY`;
- do this across six concurrent runs without understanding Bridge internals.
