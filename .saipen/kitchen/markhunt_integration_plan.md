# MARKHUNT integration plan (WIP -- phase doc written, not yet wired)

Written 2026-07-23, session low on tokens. `saipen/phases/markhunt.md`
is complete and good -- what's NOT done yet is wiring it into the rest
of the protocol so `saipen markhunt` actually works end to end. Do this
first thing next session, follow the exact ritual this whole segment
used for every other phase-shaped addition (see CHANGELOG v7.33.0,
v7.36.0, v7.40.0 for the pattern -- RFC + phase doc + CONFORMANCE row +
fixture + guides, then full ship ritual).

## Remaining work, in order

1. **RFC.md § 1.6 phase enum**: add `MARKHUNT` to the 14-value enum
   (becomes 15). Entered from ANY phase like CLEAN/TRANSLATE/VALIDATE
   -- extend the existing sentence right after the transition-table
   block ("CLEAN, TRANSLATE, and VALIDATE are entered by explicit user
   command ... from ANY phase") to include MARKHUNT. Transition table
   row: `MARKHUNT -> DONE | BLOCKED` (mirrors CLEAN/TRANSLATE's own row
   exactly -- dry audit, nothing else to route to).

2. **RFC.md § 1.10 Command Surface**: add a line for `saipen markhunt`
   near `saipen validate`/`saipen clean`, same shape as the other
   explicit-trigger commands:
   `- \`saipen markhunt\` -- dry exhaustive audit, records findings to
   BOARD.md, never fixes anything (\`phases/markhunt.md\`).`

3. **RFC § 2.1 Autonomous Transitions**: needs its own bullet, mirroring
   the existing CLEAN/TRANSLATE bullets exactly (explicit-trigger only,
   sets `phase: MARKHUNT`, loads `phases/markhunt.md`, executes it).

4. **tools/validate.py runtime manifest**: no change needed -- phase
   docs have never been part of the 12-file manifest (confirmed this
   session). The orphan-phase-doc WARN this validator prints for
   markhunt.md right now is expected and will resolve itself once
   step 1 lands.

5. **CONFORMANCE.md**: new scenario row (would be #27) -- "MARKHUNT
   records findings without fixing/capping, unlike HUNT" -- behavioral,
   README-only fixture at `tests/scenarios/markhunt-dry-record-only/`,
   same shape as every other behavioral row (see `extension-absence` or
   `parallel-translate-isolation` for the template).

6. **GUIDE.md / flagship guides (EN/RU/EE/DED)**: one-line command-table
   mention, same pattern as the `saipen plan` row added in v7.40.0.

7. **Decide the BOARD.md tagging convention for real** before writing
   step 5's fixture -- markhunt.md currently says `[MARKHUNT]` prefix
   as a placeholder ("exact convention TBD"). Pick one, make
   markhunt.md's own text match exactly what gets implemented, don't
   ship it still vague.

8. **Full ship ritual** once 1-6 are done: VERSION bump (feature-level),
   CHANGELOG entry, LOG.md entries, STATE.md update, both validators,
   commit/tag/push, re-run `bootstrap/inject.ps1`.

## Why this was split across two sessions

User explicitly asked for "only the phase" doc now, citing low token
budget, and asked for this exact handoff note to be written for next
session's cold start. Not a scope-creep concern -- a deliberate,
explicit choice. `.saipen/BOARD.md` carries a short pointer ticket to
this file; `.saipen/STATE.md`'s `phase`/`next_action` were left
untouched (a different, unrelated ADD evaluation was already pending
there from an earlier session -- not this session's to overwrite).
