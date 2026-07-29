expect: fail
expect_fail_contains: tripped safety valve

Test: `goal_mode: true` with a counter at section 2.4's cap, but no
safety-valve `WAIT:` in `next_action`.

The counters ARE the tripped state -- there is no separate flag -- so an
agent resuming here would read a normal continuation and run straight past
the ceiling the valve exists to enforce.

Added in v7.101.0. The check was hand-verified when it shipped and
then had nothing standing behind it -- 93 failure paths in
`tools/validate.py`, three with a fixture. A hand test proves a
check works once; a fixture proves it still works.
