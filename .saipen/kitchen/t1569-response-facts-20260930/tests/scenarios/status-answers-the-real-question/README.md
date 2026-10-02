Test: the human asks `saipen status` and gets an answer to the question they
were actually asking.

Observed repeatedly in real sessions: almost nobody asks `status` to learn
which phase they are in -- they ask some form of *"is this in good shape, and
does anything need me?"* Until v7.80.0 the command answered only the first
kind, so an agent that had been in the conversation answered the second from
chat scrollback, and a cold agent -- the entire point of this protocol --
could not answer it at all. Anything reconstructed from scrollback is not
state, and this makes it state.

`status` MUST report, alongside phase / in-flight ticket / queue, each line
omitted entirely when empty rather than padded with "none":

- **Waiting on you** -- every open `WAIT:` and every `## BLOCKED` ticket whose
  blocker names a human decision, quoted as the concrete question. This is the
  human's to-do list.
- **Claimed but unproven** -- work finished but whose `| verify:` never ran, or
  ran only `conf: low`/`med`. "Done" and "verified" are different states.
- **Conformance** -- the last recorded `tools/validate.py` result and when, or
  plainly that none is recorded. Never re-run it: `status` is read-only and a
  validator run is work.
- **Staleness** -- how old `STATE.updated` is, when the gap is large enough to
  matter.

It MUST NOT pronounce a verdict -- not "healthy", not "ready", not "good to
ship". It states what is and is not established; the human concludes. An agent
grading its own work is the least valuable opinion available, and
`phases/verify.md`'s manufactured-confidence warning applies to prose exactly
as it does to a green check.

The failure this catches: a `status` that reads back the phase and stops, so
the two facts that actually decide whether to ship -- what is unproven, and
what is waiting on a human -- stay only in someone's head.

Behavioral, README-only: the assertion is about what an agent chooses to say,
not about file shape, so there is nothing for `tools/run_scenarios.py` to
execute and it correctly declares no expected outcome.
