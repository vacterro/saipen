# T-1471 -- the requested change is present and demonstrated

The operator's own description of the change is the body of SRC-107
(`.saipen/intake/active/SRC-107.md`). This file is the demonstration its
`user_explicit: true` verify clause asks for: every concrete thing the operator
named, mapped to where it now lives in the tree, with the measurement that
proves it is not only prose.

T-1471 ships no code of its own. It is the roll-up whose Work was cut into
bounded slices, each of which carried its own patch and its own evidence:

| slice | subject | closure |
|---|---|---|
| T-1472 | declared core-unit family: same proof, less wall time | `own_patch` |
| T-1473 | a request that parked Work cannot hand the seat back to it | `own_patch` |
| T-1474 | `saipen start` must apply the GOAL-01 Entry itself | `own_patch` |
| T-1477 | oper-share author ideas mapped with an eligibility condition | `own_patch` |
| T-1595 | execution-time telemetry as `saipen_engine.telemetry` + `saipen stats` | `own_patch` |

## 1. "declared core-unit family ... 3475 tests, ~2254 s, baseline 47 inherited reds"

The family is a real SHIP gate, not a declaration.

- `tools/core_unit.py` exists and is the only producer of the record the gate reads.
- `tools/core_unit_baseline.json` records `ran: 4365`, `red: []` -- **zero**
  inherited reds. Any red a run reports is therefore a new red and blocks SHIP.
- 251 family records exist under `.saipen/evidence/core-unit/`.

Live run for this ticket, `.saipen/evidence/core-unit/dd8cae11347a7984-20261002T151430Z.json`:

```
verdict PASS  ran 4705  red 0  new_red []  fixed []  reused true
```

## 2. "quality fixed, time optimised under it" / "which evidence can be safely reuse[d], because the subject tree literally did not change"

This is the operator's headline ask and it is the one thing measured twice.

**Sharding (T-1472).** `.saipen/evidence/T-1472-core-unit-shards/before-after.md`:

| | wall | ran | discovered | verdict |
|---|---:|---:|---:|---|
| one process | 2037.7 s | 3580 | 3580 | -- |
| 6 shards | 763.3 s | 3580 | 3580 | PASS, new_red 0 |

`ran == discovered` in both columns: no declared test was dropped to buy the
speed. The same file records the red control
(`red-control-sharded.json`) proving a deliberate one-test red still refuses.

**Fingerprint reuse (this ticket's own run).** The run above returned
`reused: true`. It did not re-execute 4705 tests, because the subject tree is
byte-identical to the record it cites -- which is exactly the condition the
operator named. Reuse is a function of the tree fingerprint, never of elapsed
time or of the fact that a test was once observed to pass.

## 3. "SLOW_BUT_PROGRESSING / SLICE_BOUNDED / CAPABILITY_UNAVAILABLE"

The supervisor semantics the operator observed as field behaviour are named in
the shipped protocol and implemented, not just observed:

- `SLOW_BUT_PROGRESSING`, `SLICE_BOUNDED` -- `tools/saipen_engine/worker.py`, `saipen/RUNTIME.md`
- `CAPABILITY_UNAVAILABLE` -- `saipen/RUNTIME.md`, `tools/saipen_engine/supervisor.py`, `tools/saipen.py`
- the invariant itself, `QUALITY-TIME-01` -- `saipen/CORE.md`, `saipen/REGISTRY.json`, `saipen/RUNTIME.md`, and now `tools/saipen_engine/telemetry.py` (T-1595)

The four-stage progression the operator described -- principle, CORE invariant,
supervisor semantics, field behaviour -- is the order these actually landed in.

## 4. "the protocol started cutting its own development into provable bounded slices"

The board is that cut. Every ticket above is a slice whose `verify:` clause is a
command or a measurement, not an intention. T-1471 itself owns no delta for
exactly this reason: the proof is the sum of its children's proofs, and a
parent that re-wrote a child's evidence to look complete would be the failure
mode this protocol exists to prevent.

## What this does NOT claim

The operator also named **T-1464** (model-agnostic quality-retention matrix) as
work still ahead. It is open and BLOCKED at BOARD line 249, blocker
`ACTIVE_DEPENDENCY:T-1446`. It is not one of T-1471's declared `needs:`
(T-1473, T-1462, T-1497, T-1503 -- all DONE), and it is not claimed here. Naming
it is not closing it: it owes a live matrix across the available providers, and
that measurement has not been taken.