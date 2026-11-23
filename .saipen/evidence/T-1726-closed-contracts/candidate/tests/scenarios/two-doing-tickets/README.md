expect: fail
expect_fail_contains: tickets in ## DOING

Test: two tickets claimed at once. RFC section 1.11 allows at most one
`## DOING` in total -- not one per agent, since Core's model is a single
writer. Without this the failure is ticket-hopping: claim T-12, drift, claim
T-27, drift, and now three tickets are half-owned and the log is unreadable.

Added in v7.101.0. The check was hand-verified when it shipped and
then had nothing standing behind it -- 93 failure paths in
`tools/validate.py`, three with a fixture. A hand test proves a
check works once; a fixture proves it still works.
