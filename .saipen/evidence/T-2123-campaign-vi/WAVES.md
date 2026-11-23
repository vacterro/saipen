# CAMPAIGN VI (SRC-440) MODE 2 post-install hardening — wave record (T-2123)

Source: SRC-440 (SAIHANDOFF CAMPAIGN VI, operator snapshot 2026-11-20 ~23:43Z, SAIPEN_20.11.26-T23-43-13.zip).
Executed 2026-11-21 at source_head c6b779715707cc61fbe45a7057beefd736bc07a8 (tree git-delta-v1:b13b1eb9...).

## Wave A — read-only runtime/authority audit: DONE (measured)
- Runtime: scheduled-source source-checkout 8.1.0, generation gen-sha256:9718c86a379121faeebece87835f02e8931b34c7dd4b1fa9d8d62a889e22decb (matches the handoff's claimed home identity `9718c86a`).
- Policy: mode degraded / DEGRADED_ALLOWED, source operator (C:\Users\vac34\.saipen\authority.json).
- Authority broker: NOT running; expected generation svc-0761d1eb59052fa4536ecb29; identity_supported true. Degraded mode is operator-admitted; no silent escalation observed.
- Machine runtime: MACHINE_RUNTIME_READY (C:\ProgramData\SAI\SAIPEN).
- Chain audit (handoff claim) re-confirmed live from git + memory: 40794b15d -> 18d9e36d2 -> 6d154707b -> 8ff8baeda -> 26c00900c; validate receipts this session: receipt-a3e6c322c988 (6e4cf7d01), receipt-2119b1967687 (c6b779715).

## Wave B — fail-closed red_owners admission guard: DONE (committed + measured)
- Implemented by T-2122 (commit 6e4cf7d01, DONE E-22148): `_red_owners_attribution_problem` with CLOSED disposition vocabulary {undecided, resolved}, malformed-shape refusals, journal-witnessed resolved.
- Evidence: measured executed regression pair regression-execution-5058c38cba5043df834d375cab5fe662 (FAIL 10 pre-fix -> PASS 13/13 at HEAD); adversarial corpus tools/test_t2122_red_owner_fail_closed.py 13/13 green at both 6e4cf7d01 and c6b779715; T-2118 corpus green with T-7 witness row; full family new_red 0 (E-22138 fingerprint 41ea5ad3cf71ba85).
- Adversary scenarios (saihunt/saitest second pass) re-measured: enormous disposition, empty map, forged-witness splice, string top-level, genuine-witness control — all fail-closed/designed-allow, none bypassed.

## Wave C — delta-class bypass investigation: NO BYPASS FOUND (measured controls)
- delta_class is DERIVED, not declared: `core_unit._current_cycle_delta_class(ticket, events)` reads the ticket's own journaled cycle boundary text (focused admission at core_unit.py:1361 admits focused evidence only when the derived class is "source"; `None` without a boundary).
- Boundary pinned by tools/test_t2119_wa_delta_boundary.py (6 tests incl. `test_delta_class_reads_only_the_boundary_reason`), green in BOTH focused runs this session (65/65 twice).
- A model-supplied or fabricated delta-class string has no admission route: the class never becomes input, it is reread from the journaled boundary at every gate evaluation.

## Wave D — REGISTRY WAIT_USER_DECISION gap: GAP IS NAMING-LEVEL ONLY; ENFORCEMENT HOLDS
- Measured: saipen/REGISTRY.json carries NO WAIT_USER_DECISION surface entry (grep empty) — the recorded gap: the registry does not name the wait-decision route.
- Enforcement is mechanical and covered: `ticket unblock <T-###> <decision>` requires the lifting decision as argv; `decision_request.validate_authority_escalation` rejects bare `cc`/`cc all` supersession claims without operator_carrier provenance; WAIT_USER_DECISION covered across tools/test_cold_recovery.py, test_external_authentication_contract.py, test_external_revalidation.py, test_finding_invalidated_closure.py, test_supervisor.py, test_t1327_zero_manual_recovery.py; 'cc all' referenced by 84 test-side control points. Parked WAIT_USER_DECISION rows stayed unclaimable all session (topmost-workable enforcement refused stepping onto them without --explicit and evidence).
- Registering a registry-level WAIT_USER_DECISION operator input would be a protocol change (REGISTRY + COMMANDS surface) — NOT invented here; recorded as the wave's honest disposition.

## Wave E — truthful T-2120 lifecycle: VERIFIED ALREADY DONE (receipt re-read live)
- .saipen/recovery/conformance/2026-11-20T22_15_25.342167Z_receipt-21e080f705f8_core_PASS.json: status complete, blocking problem_count 0, warning_count 6, ruleset v2 fingerprint 9a47d608ed3f3a833348aaeeca5cd9e9076f3bf53b1ef92b6ade46958e3e3fec. Fresher conformance also green: receipt-2119b1967687 PASS at c6b779715.

## Wave F — SRC-386/T-2016/T-2121 single-obligation model: DECISION DELIVERED
- T-2016 (execute the SRC-386 audit inbox) is the ONE obligation owner; T-2121 exists ONLY to reissue the retired receipt (SRC-439) so T-2016 can bind a live source instead of the tombstoned SRC-386 (E-19341 ORPHANED_RECEIPT).
- Single-obligation model: complete T-2121's reissue (recovery/reissue of the archived SRC-386 bytes via the official path), then T-2016 binds the restored receipt as its single obligation source; no double-execution, no second inbox consumer. Both remain separate workable tickets (P1/P2) on the board; this campaign wave records the model, it does not execute their bodies.

## Wave G — measured performance continuing: MEASURED, NO REGRESSION AT BASELINE SCALE
- Fresh `saipen status --view agent --json` same-machine same-session medians: 6019 ms, 6410 ms, 6119 ms (median ~6.1 s) under an actively loaded session (evidence churn, focus runs earlier).
- Recorded baselines: T-2101 patched median 3.881 s, T-2105 median 3.419 s (quiet-window, --view agent); T-2108 repo-full 10.53 s p50 vs installed 11.78 s p50. Current numbers sit inside the recorded envelope; no fixation claimed, performance tracking continues as its own standing program.

## Safety rules (handoff §14) honored
- No model_supplied upgrade to host authority this cycle: SRC-438 stays chat-mediated model_supplied; all privileged surfaces (release/install) remain behind real operator confirmation; the authority broker was only READ, never started or mutated.
