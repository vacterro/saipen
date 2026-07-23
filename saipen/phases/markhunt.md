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
   building this that they stopped registering as a problem -- "that's
   just how it is" IS a finding, not an excuse to skip one. Over-capture
   beats under-capture here -- this is the one category HUNT never
   looks for at all.

Still evidence-based, same as HUNT and PLAN: a real, cited fact
(file:line, a command's actual output, a quoted contradiction between
what a doc claims and what the code does) for every finding. No cite,
no ticket -- "probably," "seems like," and "looks suspicious" are
vibes, not evidence, and MARKHUNT doesn't hallucinate findings just to
look thorough.

**Recording -- `## BLOCKED`, never `## TODO`.** Every finding becomes a
ticket appended to `## BLOCKED` on `BOARD.md`, tagged `[MARKHUNT]`,
evidence cited inline (`| blocker: unvetted audit -- <file:line or
command output>`). NEVER `## TODO` -- MARKHUNT's entire output is
unvetted by construction (uncapped, over-capture-biased, no human has
looked yet), and `## TODO` is exactly what the normal Pick Rule works
from on the very next bare `continue`. Landing raw audit output there
would let an agent start autonomously fixing things nobody asked for or
agreed were worth fixing. Triage -- moving a specific ticket to
`## TODO`, dropping the `unvetted audit` blocker -- is a separate,
later, explicit human/user step, never something MARKHUNT or a
subsequent `continue` does on its own. Group related findings under one
ticket rather than one-ticket-per-trivial-nit -- the board stays
readable, not a wall of noise. Append only -- never reorder or edit
existing tickets.

**Goal Mode brake.** MARKHUNT never increments `goal_waves` or
`goal_tickets` (RFC § 2.4) -- its findings are unvetted, so nothing may
treat finishing a MARKHUNT pass as a waypoint to keep running through.
The brake itself lives in `phases/done.md`, not here: as long as any
`[MARKHUNT]`-tagged ticket sits in `## BLOCKED`, `done.md`'s own
Goal-Mode-Empty-Board step refuses to auto-proceed to `HUNT` even under
`goal_mode: true`, and halts for the user instead. MARKHUNT itself just
transitions to `DONE` like any other phase (§ 2.1) -- it never needs to
know or check `goal_mode` directly; leaving `[MARKHUNT]` tickets behind
in `## BLOCKED` is what holds the brake. `goal_mode` itself stays
whatever it already was, untouched, until every such ticket is triaged
out.

**Long-running, so checkpoint like one.** An exhaustive, uncapped pass
can outlast a single context window. Before that happens (a context
budget warning, or after finishing each scope category above), overwrite
`.saipen/kitchen/markhunt_progress.md` with what's scanned, what's left,
and the running finding count -- overwrite, never append, it's a
cursor, not a history (history is `LOG.md`, as always). Hitting a
budget risk mid-pass: LOG a partial-completion line, leave
`STATE.phase: MARKHUNT` (not `DONE`), `next_action: "saipen markhunt"`
-- a successor resumes from the progress file's cursor instead of
restarting the whole surface from zero.

**Completion**: LOG one Event Graph line per RFC § 1.2 -- `- DATE
[E-###] [parent: E-###] RUN: markhunt -> N findings recorded` -- then
transition to `DONE`. `DONE`'s own existing priority logic
(`phases/done.md`) takes over from there for whatever's actually in
`## TODO` -- MARKHUNT's own `## BLOCKED` findings sit untouched until a
human triages them. MARKHUNT never decides what gets worked next; it
only makes sure nothing stays invisible.
