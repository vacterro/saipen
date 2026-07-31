Test: Agent without filesystem write capability sets `mode: read-only` (RFC § 1.3) and MUST NOT enter `INIT`, `PLAN`, `ADD`, `BUILD`, `SHIP`, `CLEAN`, or `TRANSLATE` -- it may only read, analyze, and report a recommended `next_action`. This fixture's `phase: BUILD` + `mode: read-only` combination is itself one violation the validator MUST catch; the fixture is a sample from the full seven-phase ban, not the whole list.

expect: fail
expect_fail_contains: read-only MUST NOT enter BUILD

Its `next_action` was not one of RFC § 1.2's five executable forms until
v7.101.0, and passed only because the prefix rule was a WARN. Corrected to
match this fixture's own `phase`/`task`, so it exercises exactly the
condition it names and nothing else.
