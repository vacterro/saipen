Test: `STATE.md` is lost/stale mid-`goal_mode` run (`goal_waves`/`goal_tickets` unknown). Agent must rebuild both by counting wave/ticket-completion events in `LOG.md` since the goal's pivot `DEC` line (RFC § 1.5) instead of assuming `0` -- assuming `0` would let a run that's already near the safety-valve cap silently get another full 3 waves / 20 tickets.

expect: pass
