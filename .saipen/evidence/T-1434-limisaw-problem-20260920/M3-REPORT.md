# T-1434 / SRC-088 — Milestone 3 evidence: stale source retirement

Date: 2026-09-20. Session astra. Phase BUILD. Continuation of SRC-088.

Mission: a stale, non-actionable Source receipt must leave CURRENT conformance
gating through a canonical tombstone path that deletes NOTHING: original bytes
preserved in cold storage, immutable retirement record, eligibility that
refuses whenever an unresolved actionable requirement would be discarded.

## Defect reproduced before patch

- LIMISAW SRC-007 was an ACTIVE external-audit receipt with a dead body-digest
  identity (SOURCE_CORRUPTION) and zero requirements, linked to no Work. The
  validator emitted 2 current FAILs (source receipts x2). No canonical
  operation could retire a source on its own; `retire` existed only as a
  ticket-scoped transaction (ticket_id + board_record required), and every
  retirement reason in the closed set was ticket-classed
  (MISROUTED_PROJECT_BINDING, TEST_FIXTURE_CONTAMINATION). The receipt could
  therefore poison conformance forever.

## Implemented primitive

Command (public, registered, guard-canonical):

    saipen source retire <SRC-###> --reason
        EMPTY_STALE_SOURCE|STALE_CREDENTIAL|SUPERSEDED_SOURCE|
        ORPHANED_RECEIPT|MISROUTED_PROJECT_BINDING
        [--successor SRC-###] [--note TEXT]

Semantics:
- eligibility is proven per reason and NEVER discards actionable work: any
  unresolved actionable requirement refuses
  SOURCE_RETIREMENT_NOT_ELIGIBLE with the first requirement named and one
  lawful next action (`saipen source disp <SRC> <RID> <DISPOSITION>
  [--evidence E-###]`);
- a broken body-digest identity has exactly ONE provable reason class:
  STALE_CREDENTIAL. EMPTY_STALE_SOURCE/ORPHANED_RECEIPT may not bury it;
- SUPERSEDED_SOURCE requires an existing successor (active or tombstoned);
  MISROUTED_PROJECT_BINDING requires a --note naming the true owner;
- the transaction copies the ORIGINAL body bytes to
  `.saipen/archive/retired/SRC-###.md` UNCHANGED (corrupt digest included),
  records both `recorded_sha256` and `measured_sha256` plus
  `digest_mismatch: true`, copies meta/contract/coverage, deletes only the
  hot intake surface, writes the tombstone and the index in the SAME
  journaled plan as LOG + STATE. Nothing is physically erased from history;
- idempotent: an identical repeat returns ALREADY_RETIRED with zero writes;
  a different tuple refuses and never rewrites the tombstone;
- validator integration: retired tombstones are validated by their own closed
  receipt-only shape, and the archived body is checked against the MEASURED
  digest so cold storage may not "fix" corruption.

Files (this change):
- tools/saipen_engine/retirement.py (SOURCE_RETIREMENT_REASONS,
  source_retirement_errors, source_only_retirement_targets,
  receipt_only_tombstone_errors + meta branch, archived-body measured check),
- tools/saipen_engine/operations.py (plan/apply source retire),
- tools/saipen.py (source retire dispatch + usage),
- saipen/REGISTRY.json (SOURCE_RETIREMENT_NOT_ELIGIBLE),
- saipen/COMMAND_EFFECTS.json (source retire = EXECUTION),
- tools/test_source_retirement.py NEW (8 cases).

## Verification (current bytes)

- `python tools/test_source_retirement.py` -> 8/8 OK: empty stale source
  (bytes preserved, tombstone, idempotent duplicate with zero rewrites),
  VERIFIED-only source as orphan, UNKNOWN and BLOCKED requirements refuse
  naming the route, SUPERSEDED_SOURCE requires a real successor, corrupt
  digest retires only as STALE_CREDENTIAL with the tampered bytes preserved
  and both digests recorded, MISROUTED requires the note, unknown reason
  refuses before any read, orphan recovery surface stays read-only clean.
- Neighbors: test_source_receipts 63/63 (carriers cleared; carrier-set run
  keeps the recorded T-1361 environment cluster), source_retirement ruff clean.

## Real LIMISAW acceptance (canonical operation only, carriers cleared)

`saipen source retire SRC-007 --reason STALE_CREDENTIAL --note "body digest
identity dead; SRC-006 corrective work already consumed by T-47/T-51; zero
requirements"` -> RETIRED, E-655, archive_ref
`.saipen/archive/retired/SRC-007.md`.

Validator after: 24 problems (was 25 with 2 source FAILs; the SRC-007
SOURCE_CORRUPTION and credential-gate FAILs are gone entirely and no new
class appeared). Remaining, each owned: 21 closure-evidence (M1 work
reverify, executed in M7), 1 improve report + 1 sweep-ticket-link (M4), 1
closure-provenance generation-move for EX-000001..3 -- the DESIGNED rollback
semantics: the engine moved after resolution, so M7 re-resolves on the frozen
final generation. Zero LIMISAW product source touched.

## Milestone exit check

- historical source damage remains visible (cold copy + digests + tombstone)
  while a proven retired source stops poisoning CURRENT conformance: yes;
- no history is deleted and no immutable byte is rewritten: yes;
- unresolved actionable requirements can never be silently discarded: yes.

## Exact next action

M4 (SRC-088): strict improve-cycle finite terminalization + sweep-ticket
linkage producer/derivation; LIMISAW improve cycles
imp-vacterro-limisaw-20260918-1/3/4 as the real fixture.
