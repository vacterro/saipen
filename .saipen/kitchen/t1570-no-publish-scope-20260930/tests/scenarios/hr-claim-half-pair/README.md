expect: fail
expect_fail_contains: INVALID claim

Hostile-regression P0: a ## DOING ticket with a half claim pair (owner without
claim_time, or vice versa) or a non-UTC claim_time is INVALID and must fail
closed at the gate -- CORE's both-or-neither rule, decided by the ONE
claim_status classifier.
