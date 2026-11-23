# T-1954 SCOUT -- independently reproduce or reject saihunt/HUNT-016

Ticket shape: a Core REVIEW hypothesis, not accepted fact. The deliverable is a
verdict on HUNT-016's finding 2 -- not a patch. HUNT-016 says
`operations.record_producer_integration` is a functioning writer with zero
callers, shadowed by the live `producer_integration` path at
`producer.py:2155`. Either that is true on this tree or it is not.

## What the ticket asks

- Reproduce or reject the hypothesis independently, on the current tree.
- Record a Core disposition.
- Apply no package patch during intake.

saihunt proposes `payload: []`, so there is nothing to integrate even if the
finding holds. The question is whether the finding is real.

## Instrument and control

`git grep` over the tracked `tools/` tree -- not a filesystem walk, so an
untracked scratch copy under `.saipen/evidence/` (of which there are several)
cannot inflate the census.

- **Suspect:** `record_producer_integration`
- **Positive control on the same instrument:** `record_crew_run`, which HUNT-015
  claimed was reachable and which must therefore show both a definition and a
  caller. If the positive control also reported zero callers, the census itself
  would be broken and no conclusion would be available.

## Measured

Suspect (`git grep -n record_producer_integration -- tools/`):

```
tools/saipen_engine/operations.py:26460:def record_producer_integration(
```

One hit, and it is the definition. Zero callers.

Its only helper (`git grep -n _plan_producer_integration -- tools/`):

```
tools/saipen_engine/operations.py:26272:def _plan_producer_integration(
tools/saipen_engine/operations.py:26494:    plan = _plan_producer_integration(
```

Two hits: the definition, and the orphan's own call. So the helper is not an
independent entry point that reaches the writer some other way.

Positive control (`git grep -n record_crew_run -- tools/`):

```
tools/saipen_engine/crew.py:1490:    `operations.record_crew_run` had no caller, so a sensor stage (SC-2 for
tools/saipen_engine/crew.py:1499:    from .operations import record_crew_run
tools/saipen_engine/crew.py:1546:    return record_crew_run(
tools/saipen_engine/operations.py:26204:def record_crew_run(
tools/test_t1430_crew_run_receipt.py:5:`operations.record_crew_run` had no caller and no verb reached it: the only
```

The control finds a definition at `:26204`, a local import at `crew.py:1499`
and the call at `crew.py:1546`, plus a test module written for that exact
question. The instrument works: it separates a reachable writer from an
unreachable one on the same tree in the same run.

The live path is also confirmed to be a different writer, not this one
(`git grep -n '"producer_integration"' -- tools/saipen_engine/producer.py`):

```
tools/saipen_engine/producer.py:2155:                "producer_integration",
tools/saipen_engine/producer.py:2164:                    "operation": "producer_integration",
tools/saipen_engine/producer.py:2201:                        "operation": "producer_integration",
```

Those are string arguments to `run_mutation` with its own `receipt_metadata`,
its own `op_id` derivation and its own finalizer hook -- it never calls
`record_producer_integration`. Two writers, one reachable.

No CLI verb reaches the orphan either: searching `effects.py` and `saipen.py`
for `producer_integration` returns nothing, so the "no caller" result is not
merely "no Python caller" -- the verb surface does not reach it either.

## Verdict

**REPRODUCED.** HUNT-016's finding 2 holds on b152e6de, by an instrument whose
positive control behaved correctly in the same run.

Magnitude, stated honestly: this is dead weight, not a live defect. Nothing
calls the function, so no receipt today is wrong. What HUNT-016 correctly
identifies is a maintenance trap -- the `producer_integration` receipt
contract has two implementations, no test covers either, and a reader or a
model repairing the live path can edit the dead one and see green.

## What the disposition is not

- It is not a licence to patch during intake (`payload: []`; the ticket says so
  explicitly).
- It is not a new finding: HUNT-015 raised it, T-1725 reproduced it on
  2026-10-16 and closed as review-only without applying the wire-or-remove
  instruction. This ticket is the third measurement of the same fact. The
  disposition should say that plainly rather than presenting it as fresh.
- It is not a claim about signals 2-5. HUNT-016 bounded itself to this surface
  and so does this pass.

## Neighbour checked

`tools/test_t1430_crew_run_receipt.py` is the precedent for what "reachable"
means in this codebase and what a test for it looks like. It exists because
`record_crew_run` had exactly this problem once and was fixed by wiring a
caller. That is the shape the orphan's resolution should take, if Core chooses
to wire rather than delete.

## Commands used

```
git grep -n "record_producer_integration" -- tools/
git grep -n "_plan_producer_integration" -- tools/
git grep -n "record_crew_run" -- tools/
git grep -n '"producer_integration"' -- tools/saipen_engine/producer.py
python -m unittest tools.test_t1430_crew_run_receipt
```
