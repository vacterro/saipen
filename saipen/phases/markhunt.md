# Phase: MARKHUNT (dry, exhaustive audit -- record only, never fix)

Tax-auditor mode: find everything, including what the project's own
maintainers have gone blind to from familiarity -- never HUNT's cheap
6-category sample, never capped, never fixes anything itself. Triggered
only by explicit user command (`saipen markhunt` / bare `markhunt`),
from ANY phase, same as CLEAN/TRANSLATE/VALIDATE (RFC § 1.10).

**Dry means dry**: MARKHUNT MUST NOT edit, delete, or fix anything it
finds -- not even the "obvious junk, delete free" allowance HUNT has.
Every finding becomes a recorded ticket, full stop. If it's tempting to
just fix something small while you're in there -- don't; that's HUNT's
or BUILD's job, not this one's. Mixing "found" with "fixed" is exactly
what makes a real audit untrustworthy.

**No cap, no sampling.** HUNT stops at 5 tickets on purpose -- cheap,
frequent, bounded. MARKHUNT is the opposite: it exists specifically for
the times HUNT's own cap or its 6 mechanical categories aren't enough,
and the user wants an outside-auditor pass that doesn't stop just
because it found enough to look busy. Keep going until the surface is
actually exhausted, not until some round number feels sufficient.

**Scope -- broader than HUNT's six, not a replacement for them:**
1. Everything HUNT already checks (failing tests, unverified commits,
   stale TODO/FIXME/HACK, silent failures, symmetry gaps, dead code) --
   MARKHUNT re-runs these too, without the cap.
2. Cross-file consistency: does every doc (RFC, phase docs, CONFORMANCE,
   README, guides) still describe what the code actually does? Stale
   claims, orphaned references, doc drift from real behavior.
3. Security posture: secrets handling, destructive-op confirmation
   gates, anything that quietly weakened since it was last reviewed.
4. Architectural debt: design inconsistencies, half-finished patterns,
   copy-pasted logic that should have been unified, abstractions that
   never got followed through.
5. Familiarity blindness: things so normalized to whoever's been
   building this that they stopped registering as a problem -- the
   entire reason an outside-auditor pass exists at all.

Still evidence-based, same as HUNT and PLAN: a real, cited fact
(file:line, a command's actual output, a quoted contradiction) for
every finding, never a hallucinated or invented problem just to have
something to report.

**Recording**: every finding becomes a `TODO` ticket on `BOARD.md`,
tagged so it's identifiable as unvetted audit output rather than
already-triaged work -- `[MARKHUNT]` prefix in the ticket line (exact
convention TBD, see integration note in `.saipen/kitchen/`). Group
related findings under one ticket rather than one-ticket-per-trivial-nit
-- the board stays a to-do list, not a wall of noise. Do not
reprioritize or reorder existing tickets to make room -- append per
normal board-order rules.

**Completion**: LOG one Event Graph line per RFC § 1.2 -- `- DATE
[E-###] [parent: E-###] RUN: markhunt -> N findings recorded` -- then
transition to `DONE`. `DONE`'s own existing priority logic
(`phases/done.md`) takes it from there -- if tickets are now sitting in
`TODO`, the very next `saipen continue` picks one up normally. MARKHUNT
itself never decides what gets worked next; it only makes sure nothing
stays invisible.
