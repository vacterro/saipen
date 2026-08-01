expect: fail
expect_fail_contains: newest goal marker rebuilds

Test: a bare `saipen goal` re-authorization reset `goal_waves`/`goal_tickets` to `0` and left no line saying so. The bumps it cancelled are still in the LOG, so the newest goal marker is the older `DEC: goal pivot`, and § 1.5's rebuild counts 2 waves and 4 tickets against a `STATE.md` that says 0 and 1.

That gap is why this fails. On the next crash Recovery resumes the run on the rebuilt number, restoring counters the human already re-authorized away -- and at or over the cap that re-trips the valve while RFC § 2.4 forbids tidying the counters back down. The re-authorization expires at the first Recovery, and every later one revokes it again from a count that only grows.

Its twin `goal-reauthorization-trace` is the same LOG with the `DEC: goal reauthorized -- goal_waves N->0, goal_tickets M->0` line present, and passes. The pair is the check's red control: the only difference between them is whether the reset left evidence, not how any check is worded.
