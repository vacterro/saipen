expect: fail
expect_fail_contains: auto-transition HUNT

The board must be genuinely halted for this to reproduce: the check needs an
empty `## TODO` as well as `phase: DONE` and the WAIT. A first draft of this
fixture left a workable ticket on the board and validated clean, which is
the check behaving correctly -- all three conditions or none.

Note: the WAIT below carries a *valid* category on purpose. A category-less
WAIT dies on the category check first and never reaches this one -- the
reason-pin caught exactly that when this fixture was first written.

Test: `phase: DONE` with an empty `## TODO` and a `WAIT:` that is neither
the section 2.4 safety valve nor `WAIT: user brake -- <reason>`.

Section 2.1 requires that exact state to auto-transition into `HUNT` without
asking anyone, so the WAIT is a previous agent's drift. Obeying it deadlocks
the project permanently: UNBLOCK says stop, nobody is coming, and the WAIT
names no answerable question.

Added in v7.101.0. The check was hand-verified when it shipped and
then had nothing standing behind it -- 93 failure paths in
`tools/validate.py`, three with a fixture. A hand test proves a
check works once; a fixture proves it still works.
