Test: at the end of `saipen ship` (after a successful push) and at
`saipen stop`, the agent (over)writes `.saipen/kitchen/digest.md` with
exactly three short lines aimed at the human -- `done:` (what this session
shipped/did), `remaining:` (the top open `TODO`, or `nothing`), `awaiting:`
(anything parked on a `WAIT:`/decision, or `nothing`). It is overwritten each
time (a snapshot, not history -- history stays in `LOG.md`). The point is the
human opens one small file to know where things stand instead of scrolling a
long log. This is a behavioral test (agent decision-making about producing the
snapshot at the two human-facing exit points), not a structural one -- the
assertion is that both `ship` and `stop` leave a current three-line digest
behind.
