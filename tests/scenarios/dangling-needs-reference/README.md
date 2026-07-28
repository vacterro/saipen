Test: `T-002 needs: T-999` where `T-999` doesn't exist anywhere on the board. Both validators MUST flag it as a dangling reference (RFC § 1.2) -- worse than a cycle, since nothing else catches it -- while leaving `T-001`'s legitimate reference to the real `T-003` untouched.

expect: fail
expect_fail_contains: dangling needs: reference

Its `next_action` was not one of RFC § 1.2's five executable forms until
v7.100.0, and passed only because the prefix rule was a WARN. Corrected to
match this fixture's own `phase`/`task`, so it exercises exactly the
condition it names and nothing else.
