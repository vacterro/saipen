expect: fail
expect_fail_contains: missing required field: blocker

Test: a checkpoint written without a field RFC section 1.2 requires. The
state is readable and plausible; it simply cannot be resumed from, which is
the definition of not being a checkpoint (section 1.5).

Added in v7.101.0. The check was hand-verified when it shipped and
then had nothing standing behind it -- 93 failure paths in
`tools/validate.py`, three with a fixture. A hand test proves a
check works once; a fixture proves it still works.
