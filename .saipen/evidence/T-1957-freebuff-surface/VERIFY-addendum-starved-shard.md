# T-1957 VERIFY addendum -- the FAIL citation, and why it is not a regression

## What happened

Two `core_unit.py evidence T-1957` runs overlapped on this tree. The second
minted:

```
CORE-UNIT-EVIDENCE FAIL family:unit ran:None red:2684 new_red:2684 fixed:0
fingerprint:b3be1dff84c472d1
record:.saipen/evidence/core-unit/b3be1dff84c472d1-20261029T162609997108Z.json
```

2684 "new red" on the same fingerprint that had already PASSed 17 minutes
earlier is not a plausible code regression, so I read the record instead of
reacting to the number.

## The record says the harness starved, not the tests

```json
"problems": [
  "no 'Ran N tests' line: the family did not run to its summary",
  "shard 0: no 'Ran N tests' line: the family did not run to its summary",
  "shard(s) [0] never reported their discovery",
  "the run has no exact shard membership proof",
  "2684 new red outside the baseline"
],
"ran": null,
"tallied": null,
"headers": 2968,
"duration_s": 995.0,
"jobs": 6
```

Every one of those problems is a *harness* fact: a shard never reported, so the
run has no membership proof and cannot tally. `ran: null` is the tell -- a real
regression would have a test count and a set of failing test ids. Instead the
runner attributed **every test in the starved shard** to red, which is why the
number is large and why the first names are mundane (`test_core_unit_gate.*`,
`test_recovery_reachability.*`) rather than anything this ticket touched.

## The evidence it is not mine

The same fingerprint has two records:

| record | finished | verdict | ran | red |
|---|---|---|---|---|
| `b3be1dff…160934458154Z` | 2026-10-29T16:09:34Z | **PASS** | 8406 | 0 |
| `b3be1dff…162609997108Z` | 2026-10-29T16:26:09Z | FAIL | `null` | 2684 |

Identical `fingerprint` means identical tree bytes. The same bytes cannot be
both green and 2684-red; the difference is `partition_error` on the second run.

## Cause

I started the second sweep while the first was still finishing, so two sharded
runs competed for the same sandbox/copy resources (`copy_wall_s: 107.4`,
`shard_copy_wall_s: 198.3`, `duration_s: 995`). The runner's own preflight names
the outcome: shard 0 never reported. My scheduling error, not the change.

## Remedy

Re-run once, alone, with no concurrent family process, and cite that run. The
earlier PASS record remains on disk and stays citable -- I am not deleting it,
because a record is evidence of what a run did, and this one honestly recorded a
starved harness.

## What this addendum is for

So that a future reader of `.saipen/LOG.md` who sees `FAIL … red:2684` at 16:26
between two greens does not conclude T-1957 broke 2684 tests. The gate itself
refuses a starved run (`partition_error` → no membership proof), so it cannot be
mistaken for SHIP evidence by the tooling -- only by a human reading the log
line out of context.
