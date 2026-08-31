expect: pass
expect_warn_contains: repairable-protocol-drift

Test: a bare `saipen goal` re-authorization reset `goal_waves`/`goal_tickets` to `0` and left no line saying so. The bumps it cancelled are still in the LOG, so the newest goal marker is the older `DEC: goal pivot`, and § 1.5's rebuild counts 2 waves and 4 tickets against a `STATE.md` that says 0 and 1.

That gap is repairable drift, not a reason to make the ordinary validator unusable. The validator warns with `repairable-protocol-drift`; the canonical reconciliation command rebuilds the counters and records the repair before continuation. Recovery therefore cannot silently resume from an unproven STATE value.

Its twin `goal-reauthorization-trace` is the same LOG with the `DEC: goal reauthorized -- goal_waves N->0, goal_tickets M->0` line present, and passes. The pair is the check's red control: the only difference between them is whether the reset left evidence, not how any check is worded.
