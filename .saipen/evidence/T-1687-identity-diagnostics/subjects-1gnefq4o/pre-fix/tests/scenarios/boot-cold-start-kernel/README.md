Test: a cold agent (zero chat history) is pointed at `saipen/BOOT.md` for a
bare `saipen continue`. It reads only BOOT + `.saipen/STATE.md` +
`.saipen/BOARD.md` + the active `.saipen/LOG.md` tail (sealed
`.saipen/logs/LOG-NNN.md` segments are NOT loaded), then executes
`STATE.next_action` immediately -- no "what should I do?", satisfying
TEST-001. The full `RFC.md` is loaded only if a rule question arises that
STATE/BOARD/LOG plus the active phase doc don't answer. This is a behavioral
test (agent decision-making about how little it must read to continue), not a
structural one -- the assertion is that continuation works off the compact
kernel without parsing the whole constitution, which is the 2-tier promise
(KNOWLEDGE/decisions.md v5.0.0) taken one tier further.
