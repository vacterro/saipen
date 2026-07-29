Test: Agent should read git status to determine in-flight edits since last checkpoint.
expect: pass

Its `next_action` read a bare `implement feature` until v7.101.0 -- not one
of RFC § 1.2's five executable forms, and green only because the prefix rule
was a WARN. `PHASE BUILD T-010` names the same work in the form a cold agent
can actually execute, and matches the fixture's own `phase: BUILD` /
`task: T-010`.
