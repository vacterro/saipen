Test: under `execution_intent: goal` the board empties, a clean `HUNT` falls
through to `ADD`, and ADD's § 2.2 evaluation lands on a non-minimal
opportunity -- `TICKET(priority); RETURN PLAN`. ADD increments
`goal_waves` by 1 at its RETURN (RFC § 2.4, `phases/add.md`), counting
this `HUNT`->`ADD` cycle's one wave. The `PLAN` that immediately follows,
elaborating the single ticket ADD just created and counted, MUST NOT
increment `goal_waves` again (`phases/plan.md`'s carve-out) -- otherwise
one `HUNT`->`ADD`->`PLAN` chain counts the same wave twice and trips the
safety valve early. A `PLAN` run that begins a genuinely new multi-ticket
wave still increments as normal. This is a behavioral test (agent
decision-making about when a PLAN run counts as a new wave), not a
structural one -- the assertion is whether the agent counts the ADD->PLAN
chain once, not twice.
