# Phase: REVIEW

## Entry and reads

Review the current wave/ship diff. Under `mode: manual-verify`, request a human
review verdict and do not auto-transition. If
`.saipen/extensions/performance/` (or legacy `extensions/performance/`)
exists, load its required benchmarks first.

## Independent evidence

**Re-run the ticket's own `verify:` here; do not read VERIFY's claim of it.**
LOG this run. Disagreement is a finding: the tree changed, the verifier is
unstable, or the claim was false. Prove every suspicion with trace/repro and
report `file:line + what breaks`.

Agreement is not one either, on a bug fix. Re-running the same verifier
reproduces a weakened one exactly as faithfully as a sound one, so ask what the
diff did to the CHECK: did any test, fixture, oracle or verification command
move; if so, on what independent grounds; does the pre-fix FAIL belong to the
verifier now passing (`VERIFY-ORACLE-01`, phases/verify.md); and can this
verifier still see the original bug. "All tests pass" answers none of those.

## Ticket-scoped self-audit

Defect class: green verification misses defects introduced by the ticket's
implementation, or changed tests conceal them.

After the verifier and oracle checks above succeed, a ticket with an
attributable implementation delta MUST receive one focused self-audit before
SHIP. Green tests alone do not satisfy this inspection. This is the executing
agent inspecting its own implementation; never claim a second agent or human
reviewed it.

Use the exact ticket-owned diff and existing test/review evidence. Inspect
modified functions and direct callers, changed public contracts and their
relevant consumers. Check failure paths; null, empty and invalid inputs;
resource cleanup and repeated execution; concurrency/state consistency where
relevant; actual test coverage and changed fixtures/assertions; and concrete
effects on other user workflows. Follow the delta: unrelated modules need a
specific dependency or failure signal before inspection.

One pass per implementation revision. First read existing REVIEW evidence:
reuse an inspection only for the exact unchanged reviewed bytes. A return to
BUILD requires inspection of the new delta after re-verification. Closing a
ticket does not trigger another pass or a global HUNT. Reuse the retry budget
below; no recursive review-of-review Work.

Verification-only, inherited_verified and no-delta tickets record that no
implementation audit applies, without a fictional source scan.
Documentation-only changes receive a scoped consistency check of the changed
instructions, references and affected contracts.

Record concise scope, reviewed revision, result and any finding disposition
in existing REVIEW/LOG evidence; no new STATE/BOARD field or evidence schema.
Reuse available diff/test evidence. Run a focused extra test only for a
concrete uncovered failure hypothesis; do not rerun the full Core family just
to perform this inspection. This supplements the verifier, regression/oracle,
Source acceptance, security and ownership gates; none is replaced or waived.

No finding: record that result and proceed. Unconfirmed suspicion: record the
exact uncertainty; do not invent a regression, block successful Work on
speculation or create demonstration tickets. Confirmed P0/P1 within owned
scope: return canonically to BUILD, fix, reverify and review. For a confirmed
lower-priority defect outside this ticket's acceptance scope, search every
BOARD section, link an existing matching ticket or add one canonically; never
count a follow-up as already fixed. Priority cannot waive broken required
behavior or acceptance. Never expand scope, mutate foreign-owned work without
admission, or change source after DONE under the old ticket.

This inspection adds no HUNT, phase, agent, persistent queue or public command.
Converge's existing full HUNT stages F and I remain separate and unchanged.

Classify:

- P0 correctness/data loss and P1 security: fix now, route to BUILD.
- P2 reliability and P3 maintainability/tests outside current acceptance:
  link or create a deduplicated follow-up; broken required behavior still
  prevents SHIP at any priority.

Run one bounded memory-promotion check after independent evidence exists:
did this Work reveal a verified, reusable, decision-bearing, non-cheap,
non-duplicate, non-transient, safe lesson? Usually NO. If YES, upsert normally
one structured card or explicitly supersede the old card; never write a card
merely because Work finished.

Verdict is `DEC: SHIP`, `SHIP after FIXES`, or `NO -- BLOCKER`.

## Retry cap

One finding gets two review passes, identified by `file:line`: pass one finds,
BUILD fixes, pass two rechecks. Still broken on pass two means
`NO -- BLOCKER`; canonically block that ticket and continue another workable
ticket. A genuinely new finding gets its own budget. Record the count in
`review_passes:`; do not count from memory. MAINTENANCE owns the global
goal-run continuation and caps.

## Exit

When P0/P1 are clear, the applicable self-audit covers the current revision,
and all required acceptance passes, enter SHIP. REVIEW has no DONE branch. The passed ticket
**stays in `## DOING` through SHIP -- do NOT close it**; publication has not
happened. Emit `PHASE SHIP T-###`. Atomic finish moves it to DONE only after
SHIP succeeds.
