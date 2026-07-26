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
