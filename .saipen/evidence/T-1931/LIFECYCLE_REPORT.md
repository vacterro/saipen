# SRC-337 lifecycle repair and completion audit

This is a partial implementation of T-1931. The full 30-finding audit and its
cross-wave acceptance clause remain the objective. No source closure, Work
completion, publication, installed-host acceptance, or SAIPAL acceptance is claimed.

## Implemented and locally verified

- W2-001 / R014: admission and cancellation preserve incompatible/corrupt
  original state bytes. State inspection rejects invalid lifecycle identities,
  persisted counters, resource budgets and worker-attempt envelopes. Absent state
  still creates a proposal; valid state resumes without rewriting it.
- W2-005 / R018: persist original generation/attempt identity before invoking a
  worker. Catch worker failures as unknown outcomes; do not repeat on TypeError,
  exception, elapsed time, or restart. An immutable outcome receipt survives
  contention during lifecycle commit. Reconcile the same original outcome before
  another generation; malformed/binding-mismatched receipts refuse without writes.
  Process death without an outcome remains recovery-required, not retry permission.
- W2-009 / R022: COMPLETE and CANCELLED remain byte-identical under cancellation.
  New cancellation increments a durable fencing epoch; delayed worker completion
  cannot overwrite cancellation or a newly admitted campaign. A new campaign
  archives the exact predecessor state rather than erasing terminal evidence.

Partial improvements to CORE-013 and PERF-002 are also present: positive finite
closed budget dimensions, durable max_cycles, no force_new replacement of any
nonterminal campaign, and lifecycle-lock release during worker execution.
PERF-002 is not complete: SAIPAL discovery/publication still execute under the
campaign lifecycle lock. Host side-effect cancellation and native execution lease
admission also remain separate unfinished requirements.

## Evidence

`run_lifecycle_controls.py` runs the same oracle against the preserved pre-fix
subject and the current subject. JSON records bind the subject and oracle SHA256
and verify that subject bytes did not change during the run.

- `lifecycle-baseline.json` / `fixed-oracle-baseline.log`: 25 tests, 66 failing
  cases and 16 errors against the pre-fix subject. Subtests count separately.
- `lifecycle-current.json` / `fixed-oracle-current.log`: 26 tests pass. The extra
  positive test starts an actual OS subprocess and exits abruptly inside the
  worker, then verifies durable attempt identity and released lifecycle ownership.
- `campaign.before.py`: exact pre-edit rollback evidence; preserve unrelated
  pre-existing changes by reviewing a diff, never restoring it over later work.
- Scoped Ruff check passes for campaign.py and test_t1931_campaign_lifecycle.py.
- Canonical focused-unit receipt E-18442: 26 tests PASS, recorded at
  `.saipen/evidence/focused-unit/defc261d1e925b8f-20261026T063142869125Z.json`;
  SHA256 `882033eaa802d7f9fa9e44c6b2b08114319c74f1363dbcafe2df6bc86b869bf4`.
  The runner listed PID 1308 as a possible leaked process; a subsequent OS
  Get-Process lookup found no live process with that PID.
- `core-conformance.log`: full core conformance remains red (66 problems,
  61 warnings at that observation), including untracked manifest members, stale
  external provenance, missing reasoning, root-file membership and document coverage.

The original 60 campaign tests passed at initial measurement. During later
integration measurement, three host-dispatch assertions failed while another
session was editing host_iteration.py/host_dispatch.py. This is not evidence of
full-green integration. Current lifecycle evidence binds only its declared scope.
The first attempted terminal coverage update was correctly refused as
EVIDENCE_UNAUTHENTICATED: the hand-authored JSON was not an execution receipt.
E-18442 supplies canonical execution evidence; the raw fixed-oracle JSON remains
additional diagnosis, never a replacement for that gate.

## Source coverage audit

A concurrent writer set R001..R019 VERIFIED using one 18-test receipt E-18437.
That does not establish the complete repair/verification clauses in SRC-337.
In particular, current code still exposes these counterexamples or missing proofs:

- CORE-001/R001: ingress and journal capability labels still mint broad campaign
  scopes; file grant digest is not bound and compared at later protected steps.
- CORE-002..004/R002..004: lock errors and minimal acknowledgment checks are not
  proof of durable generation recovery, authenticated host identity, exact request
  digest, project lineage, or safe reconciliation after uncertain acceptance.
- CORE-005/R005: campaign authority_scope still determines publication permission;
  publication is not independently revalidated at the actual side-effect boundary.
- CORE-006/R006: a supplied qualification label and digest do not independently
  authenticate original forensic artifact qualification or publication authority.
- CORE-007/R007: a cancellation pre-check is not ordered campaign lease admission
  against a concurrent cancellation or a stale worker generation.
- CORE-008/R008: _execute_canonical_worker returns route_only, but its caller still
  emits WORKER_GENERATION_EXECUTED for a successful dictionary.
- CORE-009/R009: _verify_progress_evidence still trusts progress_verified=True
  and caller-supplied before/after values; unrelated activity is not canonical Work.
- CORE-010/R010: existing report discovery does not prove bounded advancement of
  the real SAIPAL analysis queue or durable generation-aware quiescence.
- CORE-011/R011: positive dispositions need canonical verification and terminal
  Work receipts, rather than string-shaped assertions.
- CORE-012/R012: the changed host callback result mapping needs its own controls;
  three prior integration assertions failed during the concurrent edits.
- CORE-013/R013: bounded lifecycle improvements are verified here, but the full
  authorized supersession and resource acceptance matrix is not established.
- W2-002..004/R015..017: pending/unknown dispatch reconciliation and canonical
  identity require specific controls; a generic production-gates receipt is indirect.
- W2-006/R019: complete backend protocol failure propagation is not established
  by the existing generic campaign test module.

Those clauses must remain nonterminal until their actual full requirements are
proved. R014 and R018 can instead cite the current lifecycle controls; R022 has
independent terminal immutability controls here. R020..R031 remain unfinished.
An independent completion audit must remeasure current files and all 31 clauses;
neither this report nor a coverage label grants closure.

`remaining-counterexamples.json` independently reproduces five remaining defects
against current hashed source: self-asserted progress, unauthenticated acceptance
without lineage/request digest, invented qualification reaching the mocked enqueue,
caller-asserted VERIFIED disposition, and an invalid list-shaped backend envelope
accepted as success. All probes use temporary projects and mock external effects.
They contradict blanket closure using either the 18-test receipt or our 26 local
lifecycle tests. Source coverage is deliberately limited to R014/R018/R022.
