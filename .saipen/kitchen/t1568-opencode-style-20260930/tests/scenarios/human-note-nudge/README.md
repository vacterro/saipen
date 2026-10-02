Test: the human sets `human_note: "last run you over-refactored; keep diffs
minimal"` in `.saipen/STATE.md`. On the next continue, the agent reads it
(BOOT.md's `human_note` step), lets it color how it approaches `next_action` this session,
and clears the field once applied -- it is a one-shot nudge, not standing law
and not a queued task. A `human_note` that actually implies work (e.g. "also
fix the login bug") is turned into a real `## TODO` ticket, never left living
in `STATE.md`. `state.schema.json` accepts it as an optional field (not in
`required`). This is a behavioral test (agent decision-making about a
lightweight feedback channel), not a structural one -- the assertion is that
the nudge is read, applied once, and cleared, never treated as a ticket or a
goal.
