# T-1434 / SRC-088 — FINAL REVIEW (M1..M8 as ONE protocol-recovery feature set)

Date: 2026-09-21. Session astra (continuation of SRC-088; handoff SRC-089).
Local authority: no push, no tag, no public release.

## 1. Primitive inventory (each bounded, canonical, independently tested)

| M | primitive | owner |
|---|---|---|
| M1 | `saipen work reverify` + RV-NNNNNN receipts | tools/saipen_engine/debt.py, tools/saipen.py |
| M2 | `saipen ticket resolve-external` + EX receipts, generation-bound | tools/saipen_engine/external.py, operations.py |
| M3 | `saipen source retire` receipt-only tombstone | tools/saipen_engine/retirement.py, operations.py |
| M4 | `saipen improve reconcile` (finite strict-cycle exit) + `saipen ticket reasoning` | tools/improve.py, operations.py |
| M5 | closed validator-remediation contract + typed external actions + attested-evidence downgrade | tools/saipen_engine/remediation.py, validate.py, conformance.py, debt.py |
| M6 | observe/mutation binding authority + five-class cross-repo provenance | tools/saipen_engine/paths.py, saipen.py, validate.py |
| M7 | LIMISAW end-to-end recovery (live acceptance) | evidence M7-REPORT.md |
| M8 | cross-shape index + determinism family | tools/test_t1434_cross_shape_index.py, evidence M8-REPORT.md |

## 2. Final invariants — proof mapping

1. validator never demands a nonexistent canonical remediation ->
   test_remediation_self_consistency (12/12) + live LIMISAW classes removed.
2. current-tree work verification reachable -> M1 CLI; 28 RV receipts live.
3. false attested PASS cannot manufacture authority ->
   test_attested_only_pass_never_cures_closure_evidence; `evidence_class`.
4. external implementation closes without fake local ownership ->
   test_external_resolution (10/10) + EX-000004/5/6.
5. generation move becomes non-current with finite re-resolution ->
   test_re_resolution_after_generation_move + M7.2 live.
6. stale non-actionable source leaves CURRENT gating without deleting history ->
   SRC-007 tombstone + archived bytes (sha256 4e3acc12...).
7. actionable requirements cannot be buried by retirement ->
   test_unknown_and_blocked_requirements_refuse_and_name_the_route.
8. every strict Improve cycle has a finite legal terminal path ->
   test_improve_reconcile (12/12) + cycle-4 `superseded`.
9. validator-required sweep linkage has a legal producer ->
   test_improve_reconcile T-23 writer + 7 live linkages.
10. foreign read-only observation needs no environment surgery ->
    test_foreign_observation_authority + live LIMISAW/_SAIPENVIEW.
11. wrong-project mutation remains protected ->
    test_mutation_against_foreign_project_is_refused + live refusal.
12. real LIMISAW authoritative PASS via canonical ops ->
    M7: 0 problems, CURRENT_PASS receipt-6b026968bd87.
13. LIMISAW product source unchanged -> git clean, HEAD dce172c1.
14. SRC-011 product work not consumed/fabricated ->
    R001..R004 VERIFIED preserved, R005..R015 UNKNOWN; zero SRC-011 writes.
15. historical evidence append-only -> RV/EX receipts and preserved reports
    byte-identical; only canonical append transitions.

## 3. Final test truth (residual classification)

- PATCH_OWNED: NONE remaining. The home's former untracked-manifest FAILs for
  the T-1434 files were resolved by the local commit caa96f69; the home is
  conformant (0 problems) at that HEAD; LIMISAW has 0 problems.
- PRE_EXISTING: `test_check_inventory` 5 reds at fail site 17c1825e57d0436e
  (T-1345 debt, unchanged, visible); `test_public_closure_cli` 1 red (T-7
  SOURCE_SCOPE_MISSING); LIMISAW product-suite 4 harness-check failures
  (classified in M7-REPORT: 2 fixture/oracle drift, 1 suspected environment,
  1 environmental) -- LIMISAW-side, HEAD unchanged.
- ENVIRONMENTAL: gdi_paint harness fails once inside the suite, passes
  standalone (11 checks 0 failures).
- AUTHORITY_BLOCKED: none.
- UNKNOWN: 0.

## 4. T-1361 measured improvement (for its resumption)

Shared root repaired: read-only foreign-root probes no longer refuse
PROJECT_LINEAGE_MISMATCH under inherited carriers (M6); fixture carrier
isolation from E-7692 stays. Manifestations of the observational class should
disappear on T-1361's next remeasurement; mutation-path and other-root
failures remain T-1361's. No T-1361 ticket text or dependency was rewritten.

## 5. Terminalization

Acceptance satisfied: SRC-088's mission is discharged by M1-M8 with live
evidence (LIMISAW 24 -> 0 problems; home conformant). T-1434 closes through
the canonical lifecycle (VERIFY boundary, REVIEW, own_patch DONE). Publication
remains local only.

## 6. Cold-agent recovery

Canonical recovery = read .saipen/STATE.md -> BOARD T-1434 -> evidence
`.saipen/evidence/T-1434-limisaw-problem-20260920/` (REPORT, M1..M8,
this file) -> LOG tail E-7704..E-7710+. Commits: caa96f69 carries M1-M8.
Dependency resumption: T-1361 unblocks after T-1434 DONE; its own LOG
evidence and `.saipen/evidence/T-1361-*` hold the pause state.
