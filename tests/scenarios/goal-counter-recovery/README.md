Test: `STATE.md` is lost/stale mid-`goal_mode` run (`goal_waves`/`goal_tickets` unknown). Agent must rebuild both by counting wave/ticket-completion events in `LOG.md` since the goal's pivot `DEC` line (RFC § 1.5) instead of assuming `0` -- assuming `0` would let a run that's already near the safety-valve cap silently get another full 3 waves / 20 tickets.

expect: pass

Its `next_action` was not one of RFC § 1.2's five executable forms until
v7.100.0, and passed only because the prefix rule was a WARN. Corrected to
match this fixture's own `phase`/`task`, so it exercises exactly the
condition it names and nothing else.
