# T-1754 / SRC-243 — Stability, Simplification and Product Recovery

The source is retained verbatim, SHA-256
`b773444838b996a5260e3a430cd13f1442002ab2fbbc7a12ab8b00e8486886c1`.
It requests concentrating on existing execution paths, stability, and real
exploitation, keeping v8 Concurrent Mode and v9 runtime behind closed gates,
and lists next priorities when canonically admitted. The active thread's broader
`cc all` objective remains unchanged.

## Selected existing defect

T-1753 is the first priority named in SRC-243 NEXT PRIORITIES:
`Repair the broken activation launcher path identified by T-1753.`

Measured twice on 2026-10-13: exit 127 at the first command of a session that
followed the launcher line, because `{{SAIPEN_HOME}}` serves both protocol documents
and the launcher, printing `<clone>/saipen/bin/saipen` instead of `<clone>/bin/saipen`.

T-1753 is already queued at the top of TODO. No new product capability or subsystem
is introduced; this repairs the broken execution path.

## Reuse and scope

- Repair launcher path rendering in the activation block so it names the real
  launcher for both clone and installed home layouts.
- Keep `instruction_status` reading current for both spellings.
- Maintain regression coverage without creating new framework or parallel abstractions.
- Preserve security, journal integrity, ownership, and recovery guarantees.

## Ownership and evidence

Execute existing bounded T-1753 as the implementation owner. Hand this directive
Work back through `ticket block-for` or `ticket block`. Keep SRC-243 attached to its
existing parent T-1754; child dependency and actual execution evidence provide
traceability without inventing another operator instruction.

The child must have an executed fixed-oracle regression pair and the declared
family.

After T-1753 DONE (and subsequent priorities as admitted), T-1754 independently
verifies all derived clauses. If this no-publish directive Work needs shared
implementation authority, use cohort closure or inherited verification as
appropriate; publication remains pending under no-publish policy.

## Completion limits

No Source disposition is terminal yet. The code repair, its controls, the
independent parent verification, and automatic SRC-243 closure remain required.
Other queued hardening Work stays within the original `cc all` goal.
