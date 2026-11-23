# T-1954 VERIFY -- the disposition's own claims, executed

T-1954 changes no source. So VERIFY cannot be "the fix is green" -- there is no
fix. What must be proven is that the *disposition* is true and that the ticket
did not smuggle a change in under a review label.

## Claim 1 -- the orphan has zero callers (re-measured, not restated)

```
$ git grep -c "record_producer_integration" -- tools/
tools/saipen_engine/operations.py:1
```

One occurrence in the whole tracked `tools/` tree, and BUILD read that
occurrence as the definition at `:26460`. Zero callers.

Positive control, same instrument, same run: `record_crew_run` returns five
hits including the call at `crew.py:1546`. The census separates reachable from
unreachable writers on this tree, so the zero is a measurement, not a broken
grep.

## Claim 2 -- no source file was modified by this ticket

```
$ git status --porcelain tools/saipen_engine/operations.py tools/saipen_engine/producer.py
(no output)
```

Both files the hypothesis names are byte-identical to HEAD. The ticket's
`payload: []` and its "apply no package patch during intake" instruction are
honoured: the only writes T-1954 made are its evidence files and the canonical
board/log/state rows through `saipen`.

## Claim 3 -- the live path is covered, so deleting the orphan removes no coverage

```
$ python -m unittest tools.test_v7_producer_parallelism tools.test_t1746_crew_terminal_outcome
Ran 85 tests in 13.062s
OK
```

Both modules name `producer_integration` and both pass. Conversely, a search
for the orphan's symbols across every `tools/test_*.py` returns nothing:

```
$ git grep -ln "record_producer_integration\|_plan_producer_integration" -- tools/test_*.py
(no output)
```

So no test in the tree exercises the orphan. Deleting it cannot break a test,
which is exactly why it rotted unnoticed -- and it is the fact T-1955's verify
text depends on.

## What this VERIFY does not claim

- It does not claim the orphan is harmless to leave forever. It is a live
  maintenance trap: two implementations of one receipt contract, one
  untested and unreachable, and the unreachable one is the weaker (random
  `uuid4` op_id, caller-supplied resulting identity). That is T-1955's job.
- It does not claim a fix was applied. No source line changed.
- It does not extend to signals 2-5 of the six-signal sweep; HUNT-016 bounded
  itself and so did this pass.

Confidence: **high** -- every claim above is a command whose output is quoted
verbatim, and the caller census carries a positive control in the same run.

## Disposition

REPRODUCED. HUNT-016 is accurate on b152e6de. The ticket closes on that
disposition with T-1955 carrying the actual change, because the intake label
forbade a patch and a third silent absorption of the same finding would be the
real defect.
