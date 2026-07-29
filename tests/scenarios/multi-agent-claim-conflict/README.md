Test: Agent should detect another agent's active claim (<15 mins) and refuse to touch that ticket.
expect: pass

Note on the timestamp: `claim_time` here is a fixed past date, so by the
15-minute rule (RFC § 1.4) this claim reads as *stale*, not active -- the
opposite of what the sentence above describes. That is unavoidable in a
checked-in fixture: any "fresh" timestamp goes stale the next day. The file
demonstrates the *shape* of a claimed ticket; a real liveness test has to
write `claim_time` at run time. Structurally the state is valid, hence
`expect: pass` -- the active-vs-stale decision is behavioural and not
something the validator judges.

Its `next_action` read a free-text sentence until v7.101.0 -- descriptive,
not executable, and so not one of RFC § 1.2's five forms. It stayed green
only because the prefix rule was a WARN. `saipen continue` is the real
instruction here: the Pick Rule (§ 1.6) is what refuses the claimed ticket,
and it is reached by continuing, not by narrating the intent in the field.
