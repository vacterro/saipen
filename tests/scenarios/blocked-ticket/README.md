Test: Agent should log failure, mark ticket BLOCKED, and pick next DOING or TODO.

expect: pass

Its `next_action` was not one of RFC § 1.2's five executable forms until
v7.101.0, and passed only because the prefix rule was a WARN. Corrected to
match this fixture's own `phase`/`task`, so it exercises exactly the
condition it names and nothing else.
