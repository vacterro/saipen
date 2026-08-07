# Phase: BUILD

Smallest safe change. Full code: no stubs, null/empty/error paths handled.
Match repo style even if dated; modernizing = separate ticket.

**Before writing new PROSE, ask what it makes non-conformant.** § 1.1's rule: a new section names the defect class it eliminates or it does not get written, and a restatement of a rule that already exists is cited rather than repeated. Documentation edits are BUILD work and this gate applies to them exactly as the reuse ladder below applies to code.

**Before writing new code, look for existing code, in this order:**
1. this project's own code -- a helper, a module, a pattern already here;
2. the standard library of whatever language this is;
3. a dependency the project ALREADY has (adding one is a ticket, not a
   build step -- a new dependency is a decision with a maintenance tail,
   and it does not get made in passing while fixing something else);
4. only then write it.

One pass down that ladder, not a research project: the point is to stop
the third private implementation of the same thing, not to turn every
edit into an audit. If the search costs longer than writing it would,
write it and say so in the LOG line -- an honest "looked, didn't find,
wrote my own" is worth more than a silent duplicate.
Risky edit: LOG rollback command first. **Logging a rollback is not the same
as being allowed to proceed** -- if the edit is destructive in CORE.md §1.1's own
sense (schema/database drop, mass file deletion, history rewrite, irreversible
migration, deleting user data), that section's confirmation gate governs and a
logged rollback command doesn't satisfy it. Either the active ticket itself
pre-authorizes the operation AND it's reversible, or you stop and ask
(`next_action: WAIT: destructive-op -- <the exact operation, spelled out>`,
CORE.md §1.2's category vocabulary). "Risky" here covers
the ordinary large-but-recoverable edit; anything on § 1.1's list is a
different category with a different gate.
Scope grows / neighbor broken: new TODO ticket, keep moving.
Ticket touches UI/interface work? Also load UI.md.

After BUILD: LOG one Event Graph line per CORE.md §1.2 -- `- DATE [E-###]
[parent: E-###] [T-###] RUN: build -> <what changed, one line>` -- then
checkpoint per § 1.5 (LOG already done; write `BOARD.md` then `STATE.md`
in that order) before STATE -> VERIFY. This is the one checkpoint per
ticket § 1.5 requires, not a log line per tool call or per edit -- BUILD
is usually several edits across one turn; one LOG line summarizing the
ticket's change is correct, a line per file touched is not. Can't complete
safely (unrecoverable error, no write access, the change needs a decision
only the user can make)? STATE -> BLOCKED with the facts -- never force a
broken edit through to VERIFY, and never skip the LOG line even for a
BLOCKED exit. Clean tree before BLOCKED: follow procedure in phases/verify.md
(clean tree section).