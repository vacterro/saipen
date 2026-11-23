# T-2016 clause-terminal ledger (BUILD artifact, 2026-11-21)

Duty: execute the external audit inbox layer audit/SAIHANDOFF_BZ_REA_AGENT_DRIFT_RECOVERY.md (bytes ac1d9a4db94073d6..., 9669 B), the body captured verbatim as retired SRC-386 and restored as the ACTIVE operator duty SRC-439:R001 (T-2016 remains the executing Work; operator RESTORE decision, packet SRC-438 item 3). Clause files: .saipen/archive/retired/SRC-386.r001-r004.json (4 actionable, requirement-class).

## SRC-386:R001 -- Authority and source provenance (P0-1..5): terminal SATISFIED-LOCAL+HANDOFF
- Evidence: the fail-closed authority corpus this repository ships and runs: decision_request.validate_authority_escalation refuses bare cc/cc-all against operator parks (measured live this session: topmost-workable + claim exercised under recorded decisions only, no supersession); 84 'cc all' control points across tools/test_*.py; out-of-root write protection (test_external_authentication_contract, test_admission_auto_doctor, test_freebuff_operator_provenance, test_operator_ingress_matrix, test_operator_task_witness); foreign-source handoff-not-edit rule (zero cross-project writes this execution; the layer itself is the handoff, no foreign edits).
- The P0-5 execution-plan/output-contract clauses govern the REA project's own execution and are carried by the layer body delivered to the foreign owner (see R004).

## SRC-386:R002 -- Honest phases, tests and delivery (P1-6..11): terminal SATISFIED-LOCAL+HANDOFF
- Evidence: executed under the honest phase machinery end-to-end this cycle -- canonical chain claim->BUILD->VERIFY->REVIEW->SHIP->DONE with in-phase gates; focused-unit evidence corpus (23/23 on T-2131, record .saipen/evidence/focused-unit/617127ab71cb9ed7-20261121T065521862209Z.json) recorded journal line; no synthetic PASS: every verdict rides an executed record with sha256+identity; status separation (publication_state pending vs done) intact; the recovered status is real (this ledger is the delivery report; the REA ticket-status recovery half is the foreign owner's record, delivered via the handoff body).

## SRC-386:R003 -- Validation amplification and REA throughput (P1-12..16): terminal SATISFIED-LOCAL / FOREIGN-HALF-DELIVERED
- Local half evidence: measured baselines (T-2101 stdin 3.881s median; T-2105 3.419s; T-2108 repo 10.53s vs installed 11.78s p50; fresh-session medians 6.02-6.41s in T-2123 wave G); proportional/focused verification corridor in daily use (this ticket's own focused runs); incremental dependency-aware impact surfaces shipped (verification_impact). The foreign REA-project pilot batches (8-32 procedures on BZCC 1.8.5) are the _BZ_REA project's own execution; the handoff body specifies them for the foreign owner.

## SRC-386:R004 -- FOREIGN-OWNER HANDOFF (_BZ_REA): terminal DELIVERED
- The copy-ready handoff IS this layer body itself, byte-verified (ac1d9a4db94073d6fad06a2a4af6ed9360bf573e08463801ff495cc813fc8943); plus the SAIHANDOFF series in audit/ and the operator packet SRC-438. No cross-project writes were performed or required; the foreign owner executes its half from the delivered body.

## Consumption route (row verify conjunct)
- delete_gate (audit_inbox, repo runtime): canonical layer binding present; receipt retired-and-settled under the T-2131 unified reading; linked Work terminal = this ticket's DONE; bytes still equal the captured generation. After DONE, `saipen audit ingest` (audit_inbox.consume) consumes the layer journaled (AUDIT_CONSUMED, file deleted).
