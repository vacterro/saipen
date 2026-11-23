# T-1755 / SRC-244 — apply the four hardening principles

The source is retained verbatim, SHA-256
`96ccefe8f2c0d432804ea56015e50a73992b9d2749c778c7fbc5bad43cf1ac4b`.
It requests continued hardening and supplies four directions. The active
thread's broader `cc all` objective remains unchanged.

## Selected existing defect

T-1752 is already queued and directly implements principle 4:
`intake.closable_receipts` excludes audit-bound receipts while saying audit
ingestion closes them; ingestion consumes a receipt only after it is CLOSED.
Consequently, lawful DONE Work with terminal coverage needs a hand-typed
`source close`, and continue can pick a new layer before consuming the old one.

The exact current code confirms the cycle. No new product capability is needed.

## Reuse and scope

- Keep `intake.close_receipt` / `close_finished` as the sole Source-close owner.
  Remove the audit exemption from eligibility rather than adding a second
  closer in audit ingestion.
- Preserve audit classification and journaled deletion as projections and
  consumers of canonical Source closure. Keep the original-byte digest gate,
  the terminal-Work gate and all integrity/coverage/approval checks.
- Account for the reason the exemption originally existed: CLEAN currently
  keeps rows referenced by ACTIVE receipts, while audit deletion still needs
  the linked DONE row. Pending captured audit references must retain their
  Work rows until canonical consumption, without calling a CLOSED Source ACTIVE.
- Existing BOARD scrub already binds `.saipen/intake` as a tree dependency;
  the audit binding lives there. Any added retention projection must preserve
  that read/PLAN/APPLY race protection. Do not introduce another truth ledger.
- Ordinary Work completion stays on its current paths. No release, crew,
  multi-account, feature or new framework is required by the product repair.

## Ownership and evidence

Execute the existing bounded T-1752 as the implementation owner and hand this
directive Work back through `ticket block-for`. Keep SRC-244 attached to its
existing parent T-1755; the child dependency and actual execution evidence
provide traceability without inventing another operator instruction.

The child must have an executed fixed-oracle regression pair and the declared
family. Minimum public-behavior proofs: both completion paths close a fully
covered audit receipt, the next ingest consumes the closed generation before
capturing a new layer, pending audit references survive CLEAN, and incomplete
coverage/open Work/corrupt authority/changed bytes never receive a false close
or deletion. Reuse the current receipt and audit inbox fixtures.

After T-1752 DONE, T-1755 independently verifies all five derived clauses.
No fictional personal implementation delta or inherited publication may be
claimed. If this no-publish directive Work needs shared implementation
authority, use the existing cohort closure mechanism and exact tested paths;
publication remains pending under the existing repository policy. This is
local accounting of already-authorized Work, not an added product workflow.

## Completion limits

No Source disposition is terminal yet. The code repair, its controls, the
independent parent verification and automatic SRC-244 closure remain required.
Other queued hardening Work stays within the original `cc all` goal.

Graph discovery and coverage transport are unavailable; the relevant Source,
entire eligibility function, exact consumers, retention planner and neighboring
tests were read directly. No graph completeness claim is made.
