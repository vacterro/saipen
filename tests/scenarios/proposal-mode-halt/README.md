expect: pass

Test: bare `saipen plan` finished Proposal Mode and halted. `phase: DONE`,
`## TODO` carrying the proposals it just wrote, `next_action` a `WAIT:` whose
category is `user brake`.

This is the behavioral half of the rule, and it is here because a marker check
on `phases/plan.md` proves only that a sentence is still in a file. What has to
be true is that the state Proposal Mode produces actually validates -- and for
six months it could not, from either side. Step 4 ordered `phase: DONE` plus a
halt, forbade a `WAIT:` prefix as "a violation of RFC section 1.2", and forbade
proceeding to `SCOUT`. That leaves only the four prefixes that each mean "do
this now", so the halt was recordable only as an action the agent was forbidden
to perform -- and a cold agent reading `PHASE SCOUT T-###` executes it. There is
no parked `PHASE`.

The prohibition was also wrong on its own terms. Section 1.2 restricts `WAIT:`
to three fixed forms at `DONE` only when `## TODO` is EMPTY; Proposal Mode has
just filled `## TODO`, which is why this fixture carries two tickets. Empty that
board and the state stops being this one -- the empty-TODO whitelist takes over
and `tests/scenarios/done-wait-deadlock/` is the fixture that governs it.

The reason clause after the category is not normative. `tools/validate.py`
matches `user brake` and nothing past it, so a different wording here must still
pass; a fixture that pinned the sentence would be guarding the sentence rather
than the behavior.
