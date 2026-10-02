Test: Agent should detect a cyclic `needs:` dependency, move every ticket in the cycle to `## BLOCKED` with a `dependency cycle` blocker note, and keep working other unblocked tickets instead of stalling.

expect: fail
expect_fail_contains: cyclic needs: dependencies

Its `next_action` was not one of RFC § 1.2's five executable forms until
v7.101.0, and passed only because the prefix rule was a WARN. Corrected to
match this fixture's own `phase`/`task`, so it exercises exactly the
condition it names and nothing else.
