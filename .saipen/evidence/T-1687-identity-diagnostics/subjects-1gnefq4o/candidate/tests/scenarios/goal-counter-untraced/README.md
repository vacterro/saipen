expect: pass
expect_warn_contains: goal-counter-untraced

Test: A goal_waves counter > 0 with NO trace in the log triggers a WARN. 
This validates the check without failing the whole state, since older states legitimately lack the trace lines.
