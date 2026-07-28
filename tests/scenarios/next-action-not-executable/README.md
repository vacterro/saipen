expect: fail
expect_fail_contains: STATE.md next_action does not start with

Test: `next_action` carries no legal prefix, so a cold agent cannot execute
it and CONFORMANCE TEST-001 -- the one guarantee this protocol exists to
make -- fails on a state that otherwise looks complete.

This was a WARN until v7.100.0, caught only by a blacklist of vague phrases.
`ship it` is not on that blacklist and validated clean at exit 0.

Added in v7.100.0. The check was hand-verified when it shipped and
then had nothing standing behind it -- 93 failure paths in
`tools/validate.py`, three with a fixture. A hand test proves a
check works once; a fixture proves it still works.
