# SRC-338 acceptance statement — T-1932

This is a requirement-to-evidence inventory, not a PASS certificate and not a
publication authorization. It records, for every R031/R032 obligation, what the
current tree actually proves and what it explicitly does not. Current
STATE/BOARD/LOG and immutable execution records outrank this document.

## What this Work establishes

Thirty-two SRC-338 clauses are TERMINAL (VERIFIED) in
`.saipen/intake/coverage/SRC-338.json`, each settled by the canonical
`intake.set_disposition` writer against one authenticated focused-unit record:

- record `.saipen/evidence/focused-unit/90f3464452010c08-20261026T172010956231Z.json`
- sha256 `1c307db9aea978dda9f71088d68c061ffbdb05ab917968dafcb2b07e6c016eec`
- 235 tests PASS over ten modules, journal-bound as `FOCUSED-UNIT-EVIDENCE PASS`

Settling script: `.saipen/evidence/T-1932/closures/settle_src338.py`
(result `settled=32 failed=0`, every clause `COVERAGE_UPDATED`).

The record must be regenerated whenever the tree changes: `tree_fingerprint`
covers `tools/` and `saipen/`, so any edit there stales both the record and
every clause bound to its digest. This Work regenerated the record three times
for exactly that reason, and re-settled all 32 clauses each time from the single
`SETTLE` map rather than patching individual rows.

## R031 — preserved contracts, independent red/green, explicit unverified live acceptance

| Obligation | Evidence | Status |
|---|---|---|
| Preserve existing focused contracts | `tools/test_t1932_src338_closures.py` (1,179 lines) plus `tools/test_campaign_production_gates.py` re-run inside the 194-test focused record | Met |
| Independent red-before control for every finding | Red-before: `.saipen/evidence/T-1931/remaining-after-saipal-boundary.json` records all four counterexamples *reproducing* (CORE-004 `HOST_ACCEPTED`, CORE-006 `DELIVERED_PUBLICATION` with 1 enqueue call, CORE-009 `made_progress: true`, CORE-011 `DISPOSITION_RECORDED`). That file names the pre-fix bytes of all three modules. | Met |
| Independent green-after control for every finding | `.saipen/evidence/T-1932/closures/red-controls-current.json`, regenerated against current source by `regen_red_controls.py`, `all_four_fail_closed: true`, all four refused. Its `source_hashes` are the live hashes of `campaign.py`, `host_dispatch.py`, `saipal_adapter.py`. | Met |
| Relevant declared conformance gates run | Canonical validator executed on the current tree: 70 problems, classified below. Full core-unit family gate: see the family-gate section. | Run, not green — see inherited debt |
| Do not infer live acceptance from mocks or generation counters | No mock, sandbox or generation counter in this Work is presented as live acceptance. The counterexample run states `scope: "isolated temporary projects against current source; no production enqueue, no external infrastructure, no installed-host or SAIPAL backend contact"`. | Met by refusal |
| Reconcile with T-1930 / SRC-336 | SRC-338:R001–R032 is the corrective successor; T-1930 remains DONE with its own SRC-336 receipt untouched, and no SRC-336 label was inherited. | Met |
| One authoritative state owner for overlapping findings | `.saipen/intake/coverage/SRC-338.json` is the sole disposition store for these clauses; all 32 rows carry the same record digest. | Met |

## R032 — correct the disproved T-1931 closure prospectively

| Obligation | Evidence | Status |
|---|---|---|
| Preserve the original immutable Source and history | `SRC-337` and its contract/revision files are unmodified; T-1931 remains DONE with `closure_mode: own_patch`. Only forward-looking coverage is added under SRC-338. | Met |
| Independently resolve every original SRC-337 finding | 32/32 SRC-338 clauses VERIFIED with `verification` naming the focused record. The disposition writer refuses IMPLEMENTED/VERIFIED without it. | Met |
| Do not inherit blanket VERIFIED labels from narrow or simulated tests | R019 initially returned `EVIDENCE_UNRELATED` because the first-named test file (`test_campaign_matrix.py`) did not match the clause domain; it was re-settled only after naming the test that actually exercises the adapter boundary and citing its real method names. | Met |
| Preserve tested lifecycle/backend improvements | `test_t1932_src338_closures.py` keeps the host-dispatch, campaign, journal-compaction, lock and deadline controls the earlier lifecycle work added. | Met |
| Prove the four counterexamples fail closed | `red-controls-current.json`: CORE-004 `ACCEPTANCE_UNVERIFIED` / `dispatched: false`; CORE-006 `NOT_QUALIFIED` / `enqueue_call_count: 0`; CORE-009 `made_progress: false`, `state_mutated: false`, `journal_advanced: false`; CORE-011 `DISPOSITION_UNVERIFIED` with a typed error. | Met |
| Real installed-host/SAIPAL acceptance requires actual receipts | **No receipt from a real installed host or a real SAIPAL backend exists.** None is claimed. | **UNVERIFIED** |
| All declared required gates must pass before full completion | Canonical validator: FAIL (70 problems). Family gate: see below. | **NOT MET** |

## Explicitly unverified — live acceptance

Real installed-host and SAIPAL end-to-end integration **remains UNVERIFIED**.
This is the honest state, not a pending formality:

- No receipt from a genuine installed host exists.
- No receipt from a genuine SAIPAL backend exists.
- Every counterexample and every closure control in this Work runs against
  isolated temporary projects with no production enqueue, no external
  infrastructure and no installed-host or SAIPAL backend contact.
- No mock, sandbox, temporary project or generation counter in this Work is
  evidence of live acceptance or long-duration autonomy.

R031 forbids inferring live acceptance from mocks or generation counters, and
R032 requires actual receipts. Both are satisfied by stating the gap rather
than by manufacturing a green.

## Canonical validator — 70 problems, all inherited

Command: `saipen validate --json`; receipt
`receipt-0af0b7e89bac`; verdict `FAIL`; `timestamp_utc 2026-10-26T16:18:57Z`.

| Rule | Count | Attribution |
|---|---|---|
| `runtime_manifest_untracked` | 68 | **Not T-1932.** Every one of the 68 paths is `??` in git — the runtime manifest names files that were never committed, spanning roughly forty prior tickets (`tools/test_t1815_*` … `tools/test_t1927_*`). Repairs two of them (`campaign.py`, `host_dispatch.py`) were touched by this Work, but their untracked state predates it. Clearing this class requires a commit, which needs explicit operator authorization. |
| `closure_provenance_drift` | 1 | **Not T-1932.** `EX-000022` was verified on 22.10 against engine generation `fbbb9107…`; the running engine has moved. Pre-existing; recorded as inherited in `.saipen/evidence/T-1862-readiness/REPORT.md` and `.saipen/evidence/T-1882-regression-baseline/DISPOSITIONS.md`. |
| `unclassified` | 1 | **Not T-1932.** `sweep-ticket-link` on `.saipen/improve/imp-vacuum34-saipen-20261025-1/SWEEP.md:3` — T-1909 was produced without a `recurrence:`/`weak_model:` block on 25.10, before this Work began. |

Two validator FAILs *were* attributable to T-1932 and are fixed: the
unclassified shipped documents `saipen/COMMANDS_REFERENCE.md` and
`docs/host_integration.md` now carry documented `COVERED` entries in
`tools/validate.py`, and five stray root hook artifacts (`BUILD`, `forensic`,
`prove`, `.cbmignore`, `.mcp.json`) are resolved by deletion or `.gitignore`.

## Family gate — 106 red, 36 fixed, 0 new red

The full core-unit family ran twice on this Work. Comparing the two red sets
directly is the measurement that matters:

| Run | Record | Tests | Red |
|---|---|---|---|
| Before this segment's repairs | `.saipen/evidence/core-unit/ef536a23aff0c76a-20261026T151906019684Z.json` | 8006 | 142 |
| Current tree | `.saipen/evidence/core-unit/90f3464452010c08-20261026T170745871198Z.json` | 8006 | 106 |

- **Fixed: 36** — every one is a repair this Work made or a red the stray
  `V:\_TEMP_\.saipen` ancestor binding was causing. They include
  `test_refusal_registry.RegistryCompletenessTests.test_every_production_refusal_code_is_registered`
  (the 24 newly registered codes), `test_subprocess_utf8` (the four explicit
  `encoding="utf-8"` sites), both `test_vocabulary_parity` routing rows
  (`saipen/COMMANDS_REFERENCE.md`), and the whole cluster of
  `non_saipen_project_remains_non_interfering` / `BindingControls` /
  `test_t1553_mid_session_activation` cases that the quarantined temp root had
  poisoned.
- **New red: 0.** Nothing this Work touched regressed a previously passing
  test.
- **Remaining 106: inherited.** Concentrated in `test_t1746_crew_terminal_outcome`
  (35), `test_t1750_release_boundary` (11), `test_t1817_closure_outcomes` (10),
  `test_t1844_source_event` (9), `test_source_contract_derivation` (7),
  `test_t1553_mid_session_activation` (7), `test_response_surface_contract` (4).
  Sampled root causes are other sessions' uncommitted work: `'VALIDATION_FAILED'
  != 'CREW_NOT_READY'` in the crew/release path, and a body-only crash test
  getting `ok: True SOURCE_DUPLICATE` where `ok: False` was expected.

The gate is **not a declared requirement of T-1932**: the board row carries no
`requires:` capability and `saipen test suite status` reports `declared: false`.
It was run to measure, not because it gates closure.

The baseline `tools/core_unit_baseline.json` was **not** edited by this Work:
its empty `red: []` is pre-existing working-tree state whose HEAD version holds
six `legacy_lifecycle_compat` entries that now pass. Editing it to make the gate
green would be exactly the simulated-production closure R031/R032 forbid.

The current record's flight was rejected with
`verification result does not match its requested immutable identity` because
`tools/validate.py` was edited four minutes into the run, changing the tree
fingerprint mid-flight. The record itself is internally valid
(`full_scope_problem: None`, fingerprint `90f3464452010c08…` which matches the
current tree now) and its red set is the one compared above; it is retained as
measurement, not presented as a PASS receipt.

## Honest disposition

R031 and R032 are satisfied in the only way an unreceipted live integration can
be: by refusing to infer it. The corrective clause work is complete and
independently controlled; the live installed-host/SAIPAL claim is not made and
must not be read into anything in this directory.
