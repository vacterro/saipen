# T-1752 — automatic closure of completed audit Sources

## Current-state reproduction

`pre-fix-probe.json` records canonical audit ingestion into a disposable project,
one actionable VERIFIED clause, successful ticket FINISHED, and a Source plus
audit layer still ACTIVE. This is the actual two-owner deadlock, not a theory
based on the report's wording.

## Implementation and ownership

`intake.closable_receipts` now includes audit receipts under the existing
integrity/coverage/DONE eligibility and `close_receipt` reproof. It no longer
asks audit classification whether an otherwise eligible Source may close.
The false docstring promising closure from audit ingestion was corrected.

`intake.active_receipt_works` retains pending captured audit Work references
from the existing read-only `audit_inbox.provenance_trace`. Its ACTIVE receipt
set stays exact. The validator and BOARD scrub already share this provider,
and scrub's existing `.saipen/intake` tree precondition covers the binding it
reads. The Work row stays available to the unchanged deletion gate until
canonical consumption records DELETED. Retention is conservative for any
unconsumed captured binding, including a missing transport.

The implementation delta is in intake.py; board_scrub.py has the corresponding
retention documentation update. One old test explicitly encoded the faulty
audit exemption and was corrected. Seven new public-behavior controls cover
both completion paths, old-before-new ingest order, pending retention/release,
incomplete coverage, another open Work, changed bytes and corrupt binding.
All pre-existing unrelated hunks were preserved; exact original files are in
`before/`.

## Oracle and measured evidence

The initial oracle expected continue to stop at the intermediate pending state.
The real canonical `continue-probe.json` proved that continuation executes the
next `audit_ingest` step in the same invocation: FINISHED -> Source CLOSED ->
AUDIT_CONSUMED. The final oracle therefore requires that exact trace and the
DELETED binding on continue, while the ticket-done test still requires
CLOSED_PENDING_DELETE before a separate ingest and verifies old-before-new
capture order. This correction changes no product behavior and was made
before native measurement of both subjects.

- Final focused receipts/audit/scrub checks: 43 PASS.
- Whole-source command/refusal/UTF-8 contracts and the existing continue-close
  neighbor passed in the preceding 66-case run; its sole error was the
  intermediate-state assumption corrected above.
- Ruff 0.16.0 over `tools/ tests/` and owned-path whitespace passed.
- Native execution:
  `.saipen/evidence/regression/regression-execution-7f4bf055c6b6446ca382bd13d18c0dd0.json`.
  Same final verifier
  `18ebb915d48f090e6541caf848376f314edab8fa2cb9d087465b56a31d297131`:
  original subject exit 1, 7 ran / 5 failed; current subject exit 0,
  7 ran / 0 failed. Both halves were executed and checkpointed at
  E-15916/E-15917. No attestation substitutes for those runs.
- Only the new test received an intent-to-add marker. All 5,212 foreign index
  entries and product bytes were unchanged by tracking; `index-intent.json`
  preserves the result. No commit, tag or remote was changed.
- T-1695's unchanged focused contract was explicitly re-executed: 38/0,
  RV-000057, focused CURRENT_PASS. Canonical validation of the current
  T-1752 tree then returned VALID / CURRENT_PASS, zero problems and nine
  warnings, preserved in `canonical-validation.json`.

## Family and independent review

The original family process completed PASS: 6,668 discovered and executed,
zero red/new red, no partition error, no leaked sandboxes. Typed record:
`.saipen/evidence/core-unit/e2192918fc4e2624-20261015T170253Z.json`.
The current content fingerprint still equals
e2192918fc4e2624f71c9f5a1176f4a4f7dbfb47043e422e892514b5b9668424.
REVIEW independently reran all seven owned cases: PASS, zero failures,
preserved in `independent-review.txt`.

REVIEW also measured the conservative missing-transport case: after a lawful
Source close, an externally removed capture makes ingest report clean while
the raw binding remains ACTIVE and retains the Work. This is the separate P3
T-1801, with `missing-transport-review.json` evidence; it is not declared fixed
by this Work. No P0/P1 was found. Memory promotion NO.

E-15923 records SHIP, E-15924 enters it, E-15925 binds exactly four owned
paths, and E-15926 records the no-publish ship. Final SHIP validation returned
CURRENT_PASS, zero problems and nine warnings (`ship-validation.json`).
Canonical finish `finish-711ec83f330e4600ae8c9260599b42a3` wrote T-1752 DONE
at E-15927 and resumed T-1755 at E-15928, without restoring a live claim.
The subsequent canonical continue reclaimed the parent at E-15929.
After independent parent completion, canonical bind-cohort at E-15942 preserved
this child's original finish while assigning its unpublished implementation
to shared C-006 with T-1755. Current closure mode is cohort, publication pending.
`running-job.json` records that the family and child Work are terminal; never
restart the completed run or replay its finish.

After verified child completion, T-1755 must resume and independently prove
SRC-244's five clauses and its own lawful closure. The original source body
hash was rechecked unchanged. The broader `cc all` objective is not complete.

## Discovery limitation

Graph search and required coverage calls returned `Transport closed`.
The exact eligibility/retention functions, both named consumers, existing
audit provenance and deletion gates, and relevant fixtures were read directly.
No graph completeness claim is made.
