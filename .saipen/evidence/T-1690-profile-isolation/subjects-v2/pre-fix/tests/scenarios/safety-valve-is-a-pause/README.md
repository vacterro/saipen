Test: the safety valve trips, and the run can still legally be continued.

RFC § 2.4's valve stops an autonomous run at 3 waves / 20 tickets and tells
the user to re-invoke bare `saipen goal`. Until v7.86.0 the Exit list also set
`execution_intent: normal` on a trip -- while § 1.10 recognizes bare `saipen goal`
ONLY while `execution_intent: goal`. Tripping the valve therefore made the one
documented way forward illegal, in exactly the state the trip created. The
objective could not be continued at all: only replaced by `saipen goal <text>`,
which demotes the board and re-plans. That is substitution, not continuation.

A valve trip is a budget pause awaiting re-authorization -- the same shape as
`saipen stop`, which was likewise never an Exit condition. The two real exits
(`ADD` concluding mature, session-level `BLOCKED`) are the objective actually
ending; a trip is not that.

So: the goal intent stays set through a trip. What prevents a restart from
walking straight past the valve is the counters, not the flag --
`execution_intent: goal` with `goal_waves >= 3` or `goal_tickets >= 20` IS the
tripped state. An agent resuming into it MUST re-state the stop, with
`next_action` in § 1.2's safety-valve `WAIT:` form, and wait. Bare
`saipen goal` resets both counters to `0`, and that reset is the human's
re-authorization.

Counters at or over the cap are load-bearing, not historical trivia. Never
"tidy them up" without an actual re-authorization -- that silently grants a
budget nobody approved.

The failure this catches: a valve that halts the run and leaves no legal way
to resume it, or a restart that sails past a cap because the flag alone was
consulted.

Behavioral, README-only: the assertion is about which command an agent accepts
in which state. Correctly declares no expected outcome, so
`tools/run_scenarios.py` skips it.
