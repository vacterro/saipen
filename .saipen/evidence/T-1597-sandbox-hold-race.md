# T-1597 — the held-sandbox control raced the holder it was waiting for

Found by the T-1596 drain: the declared family run of 02.10.26
(`.saipen/evidence/core-unit/4644b8dc16e3fd6f-20261002T174000Z.json`) reported
`new_red` including
`test_t1505_core_unit_sandbox_reclaim.HeldSandboxTests.test_a_held_sandbox_is_reported_then_swept_once_its_owner_is_gone`,
in shard 0 of 6. The next family run, after an unrelated budget repair, came back
`red 0 / new_red 0` — one red in 4722, unreproducible on demand.

## What was measured before naming a cause

- The test alone: 4 of 4 runs green (3.5 s each).
- The test module: 15 tests green.
- A probe that replays the test's exact sequence 12 times under six busy CPU
  processes: 12 of 12 green, stamp pid never recycled, sweep never empty.
- A probe of 120 concurrently spawned-and-exited processes: 0 pids handed back
  within 400 ms, so pid recycling is not the mechanism on this host.

So the red is load-dependent and intermittent, and **no mechanism was proven**.
Two timing assumptions in the control are the only load-sensitive lines:

1. `hold()` sleeps 0.5 s and the test then assumes the child has taken the tree.
   Nothing under six shards guarantees that; an unheld tree is reclaimable, so
   `assertFalse(reclaim(...))` can fail for a reason it never names.
2. The final `sweep_stale_sandboxes(temp)` is taken the instant `holder.wait()`
   returns. Windows releases a just-exited process's directory handle on its own
   schedule, and `reclaim` is documented to retry a few times and then REPORT.
   One sweep at that instant is a race.

## The repair

Both waits became bounded polls over the real condition, with the cause named on
failure:

- `held_within(path)` polls `reclaim` until the tree proves held, or gives up.
- `sweep_within(root)` polls the sweep until the dead owner's handle is released,
  or reports empty at the bound.

No assertion was weakened: the test still requires a held tree, a reported
reclaim, an eventual sweep of exactly that sandbox, and its removal.

## Same-oracle controls

- `test_waiting_for_a_sweep_never_reclaims_a_live_owner` (new, in the module):
  a sandbox stamped with the *current* pid is not reclaimed within the bound and
  still exists afterwards. The retry tolerates a slow handle release; it can
  never turn "owner still running" into "owner gone".
- Scratch negative control (`.saipen/evidence/T-1597-sandbox-hold-race.md`
  companion, run from a copy): `held_within` on a tree nobody holds returns
  `False` in 0.05 s and the tree is gone — the poll reports the missing hold
  instead of sleeping through it.

Module after the repair: 16 tests, all green (102 s).

## What is NOT claimed

The intermittent red was observed once. The repair removes the two timing
assumptions rather than proving which of them bit, because the proof was not
available locally: shard-level tracebacks are not kept in the evidence record.
The confirming oracle is the next declared family run at `--jobs 6`, which
executed after this repair — see the record named in the LOG entry.