Test: a fixable SHIP preflight failure may return the current ticket to BUILD
before any commit, tag, or push occurs.

This fixture is the legal structural half: `transition_from: SHIP` with
`phase: BUILD` MUST pass RFC section 1.6's DFA. `phases/ship.md` owns the
behavioral boundary: the agent logs the exact preflight failure, fixes it in
BUILD, then repeats VERIFY, REVIEW, and SHIP. A publish failure or work already
pushed cannot use this edge.

Without the edge, the only available SHIP failure exit was BLOCKED. That is
wrong for a known local fix and worse under goal mode, where reaching
`STATE.phase: BLOCKED` ends the autonomous run.

expect: pass
