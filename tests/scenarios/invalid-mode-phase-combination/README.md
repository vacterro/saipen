Test: `mode: no-publish` combined with `phase: SHIP` -- and this fixture MUST
**pass** the validator, not fail it.

It used to assert the opposite. Until v7.66.0 RFC § 1.3 read "Missing Git:
`mode: no-publish`. Agent MUST NOT transition to `SHIP`", and this fixture
existed to prove the validator caught that combination. That rule was deleted
deliberately: `phases/review.md` makes `SHIP` mandatory before `DONE` with no
exception, so banning the phase outright left a git-less project able to VERIFY
and REVIEW cleanly and then never legally close a single ticket. What
`no-publish` denies is publishing -- commit, tag, push -- not shipping;
`phases/ship.md` now has an explicit no-publish branch that runs the local
steps and closes to `DONE`.

The fixture kept asserting the dead rule for eight releases, because nothing
ever executed it (see CONFORMANCE.md's "honest status" note). Meanwhile all
three validators went on enforcing that same dead rule until v7.70.0 found and
removed it -- a git-less project was failing conformance and, via the
pre-commit hook, being blocked from committing.

So its job is now the reverse and more useful one: **a regression guard.** This
state is legal. Anything that re-introduces a phase-level `no-publish` ban turns
this fixture red -- precisely the mistake that already shipped once.

The still-live mode x phase restriction -- `read-only` MUST NOT enter
`BUILD`/`SHIP`/`CLEAN`/`TRANSLATE` -- is covered by `read-only-restriction`,
which does fail as intended.

expect: pass
