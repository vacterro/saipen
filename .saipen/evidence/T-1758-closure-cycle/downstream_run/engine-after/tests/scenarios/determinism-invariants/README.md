Test: two conformant agents given the same `.saipen/` reach the same decision.

RFC § 1.11 exists because "the agent decides" is not a specification. Four
invariants, no new files or fields:

**Fixed action priority.** RECOVER > OBEY > UNBLOCK > FINISH > START >
MAINTAIN, first match wins, no weighing. A corrupt `STATE.md` is repaired
before anything runs; a command the user just typed outranks the previous
session's pre-computed `next_action`; a `BLOCKED` session or a `WAIT:` nobody
answered is restated rather than worked around; an in-flight `## DOING` ticket
is carried forward before any new one is claimed. Previously nothing said which
of these went first, so two models facing a blocked session with a workable
ticket could legitimately do opposite things -- and `OBEY` was missing from
the list entirely, which cost this repository the same `qq` twice.

**One ticket at a time.** At most one `## DOING` in total, not per agent (RFC § 1.11; this README said "per agent" until v7.101.0, six releases after the rule changed and while `tools/validate.py` already FAILed any board with two). Core's model is one agent writing `.saipen/` at a time, so "per agent" invited the reading "that ticket is not mine, so I may claim a second". Finish it, block
it, or demote it -- with a LOG line, since walking away silently is what
produces tickets whose state nobody can determine. The failure mode is
specific: claim T-12, drift, claim T-27, drift, claim T-53, and now the log is
unreadable and three tickets are half-owned.

**Every session leaves a trace.** A LOG line, a BOARD change, a STATE change,
or a change to the project's own files. If none of those happened, the session
did nothing and must say exactly that -- not summarise its activity in chat. A
run whose entire output lived in a conversation is indistinguishable from one
that never ran, and that is the point: thinking is not progress.

**Insufficient information is a stop, not a guess.** If writing the next
action requires a sentence starting "presumably", "I'll assume", or "it
probably wants", the information is insufficient by definition -- stop with a
`WAIT:` naming the exact missing fact, within § 1.2's legal categories.

That last one is the one that matters most, and the hardest to test after the
fact: a wrong guess produces confident, well-formed, fully-logged work that
looks exactly like right work. Every other failure in this protocol leaves
evidence. This one doesn't.

Behavioral, README-only: these are decision rules, not file shapes. Correctly
declares no expected outcome, so `tools/run_scenarios.py` skips it.
