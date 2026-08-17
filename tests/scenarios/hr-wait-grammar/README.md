expect: fail
expect_fail_contains: malformed WAIT

Hostile-regression P1#5: the closed WAIT grammar is EXACTLY
`WAIT: <category> -- <one sentence>` (CORE.md § 1.2), plus the engine's own
verbatim safety-valve pause. A bare `WAIT: blocked` names the KIND of stop and
asks nothing, so it is forbidden -- it is the vague stop the grammar exists to
prevent, and it is what this fixture pins. So are a prefix collision
(`WAIT: blockedness -- fake`), a missing delimiter (`WAIT: blocked fake`), an
empty body (`WAIT: blocked --`), and a body carrying a second sentence (a stop
instruction with notes is a queue the next agent reads as work).

The full hostile matrix -- every rejected shape, all seven categories in a
normal context, and the exactly three brakes CORE permits at `phase: DONE` with
an empty `## TODO` -- is executed by `run_hostile_wait_probes()` in
`tools/run_scenarios.py`. This fixture keeps the single worst case wired to the
shared STATE validator so the portable path fails too.
