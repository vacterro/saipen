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
`goal_mode: true`, and halts for the user instead -- in § 1.2's fixed
wording for that state, which is the third whitelisted `WAIT:` and
exists precisely so this brake is machine-separable from drift. MARKHUNT itself just
transitions to `DONE` like any other phase (§ 2.1) -- it never needs to
know or check `goal_mode` directly; leaving `[MARKHUNT]` tickets behind
in `## BLOCKED` is what holds the brake. `goal_mode` itself stays
whatever it already was, untouched, until every such ticket is triaged
out.

**Long-running, so checkpoint like one.** An exhaustive, uncapped pass
can outlast a single context window. Before that happens (a context
budget warning, or after finishing each scope category above), overwrite
`.saipen/kitchen/markhunt_progress.md` -- and make it a **manifest**, not a
vague note, because this file is MARKHUNT's own closure check (the thing
HUNT gets from its exact hash-match skip and MARKHUNT historically lacked,
leaving completeness pure self-report). It MUST carry: `vectors:` (which of
the scope categories 1-5 above are actually done), `surface:` (the
dirs/globs swept, so "what was in scope" is a recorded fact, not a feeling),
`findings:` (running count), `cursor: partial | done`, and
`head_start:`/`head_end:` (the `git rev-parse --short HEAD` at the pass's
start and its end -- no git available (`mode: no-publish` or no repo at
all)? Write the literal string `no-git` in both fields instead, and the
closure self-test below skips the `head_end` equality check entirely for
this pass -- a no-git project can't produce a hash to compare against, and
that MUST resolve to "check doesn't apply," never "MARKHUNT can't run
here"). Overwrite, never append -- it's a cursor, not a history
(history is `LOG.md`, as always). Hitting a
budget risk mid-pass: LOG a partial-completion line, leave
`STATE.phase: MARKHUNT` (not `DONE`), `next_action: "saipen markhunt"`
-- a successor resumes from the progress file's cursor instead of
restarting the whole surface from zero.

**Completion -- the closure self-test (never declare done without it).**
Before transitioning to `DONE`, verify the manifest actually closes:
`cursor: done`; every scope category 1-5 present in `vectors:` (a missing
vector means the surface is NOT exhausted -- keep going, don't round up);
`head_end` equals the current `git rev-parse --short HEAD` (HEAD moved
mid-pass -> the coverage is against a stale tree, re-run the moved part) --
both `head_start`/`head_end` are the literal string `no-git` (no repo, or
`mode: no-publish`)? This check is satisfied automatically, nothing to
compare; and `findings:` is fully accounted for by the `[MARKHUNT]` tickets
this pass wrote to `## BLOCKED` -- **accounted for, not numerically equal**:
this same doc tells you to group related findings under one ticket rather
than filing one per trivial nit, so 10 findings landing as 3 grouped tickets
is the intended outcome, not a failure. What the check actually forbids is an
*unaccounted* finding: something counted in `findings:` that reached no ticket
at all. Grouping is legal, dropping is not -- so a grouped ticket MUST name
how many findings it carries (e.g. `[MARKHUNT] doc-drift cluster x6`), which
is what makes the sum checkable at all. Any finding that can't be traced to a
ticket means the pass isn't done -- resolve it,
never paper over it. This is the manifest-driven closure HUNT gets for free
from its hash line; MARKHUNT earns it by checking its own manifest. Only
then LOG the completion, carrying the manifest summary into that permanent
line so coverage stays auditable after `kitchen/` is swept: `- DATE [E-###]
[parent: E-###] RUN: markhunt -> N findings, V/5 vectors, @head_end` (this
enriched form, not a bare count). A later `VALIDATE` or a human cross-checks
it trivially -- the line's `N` must equal the findings accounted for across
this pass's `[MARKHUNT]` tickets on the board (their per-ticket counts summed,
not the ticket count itself, per the grouping rule above) and `V` must be `5`. Then transition to `DONE`. `DONE`'s own existing priority logic
(`phases/done.md`) takes over from there for whatever's actually in
`## TODO` -- MARKHUNT's own `## BLOCKED` findings sit untouched until a
human triages them. MARKHUNT never decides what gets worked next; it
only makes sure nothing stays invisible.
