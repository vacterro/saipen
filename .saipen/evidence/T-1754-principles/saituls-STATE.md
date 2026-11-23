---
phase: DONE
task: none
next_action: "saipen continue"
blocker: none
agent: saipen-cli
saipen_version: 7
schema_version: 3
style_contract: ded-069a4c52
saipen_home: "V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN"
mode: no-publish
transition_from: SHIP
last_event: 3243
updated: "2026-10-15T21:24:55Z"
execution_intent: goal
goal_waves: 0
goal_tickets: 9
continuation_authority: operator_required
authority_source: E-3128
authority_until: budget
safety_valve_mode: hard_wait
---

# T-282 / W2-002 residual ownership generation -- completed, evidence recorded

Bounded under T-260 / SRC-078 ownership; no scope expansion admitted.

Delivered in Scripts/accounts/SaiAccountsHelper.cs:
- post-write ACL witness (`post_write_acl_fp`) journaled immediately after
  `SetAccessControl`, before verification, so a mid-flight journal proves the
  ACE on disk was written by this helper.
- generation-checked rollback in `HandleGrantFailure`: a foreign ACL generation
  refuses rollback (no ACE deleted, evidence stamped and retained); rollback
  results are verified against the pre-mutation generation.
- evidence is stamped onto the existing journal (`MarkTxnIntentState`), never
  rewritten, so transaction identity and witnesses survive a failure.
- reconciler adopts `mutation_written` journals and refuses adoption when the
  recorded write witness disagrees with the live ACL.
- ensure fails closed with INCONSISTENT_GRANT_STATE when the witness cannot be
  journaled.

Tests: 38/38 (new suite), 105 + 69 + 240 + 264 regression all green.
Power-loss durability classified BLOCKED, not claimed PASS.
Publication disabled. No push, no deploy, no account changes.

T-261, T-262, T-263 remain paused. T-260 left PAUSED: other SRC-078 audit
clauses stay actionable.


# T-273 SAISPIN watchdog repair -- work completed (board-blocked, not finished)

All P0 and P1 acceptance criteria implemented and verified:

### P0-1: Producer authentication (FIXED)
- `validate_lease_producer_authority()` now requires `producer_token` matching
  a `producers.json` registry entry; hand-written leases with no matching
  token are refused.
- `build_managed_lease()` accepts and embeds `producer_token`.
- `register_managed_worker()` generates UUID4 token, records it in registry.
- PowerShell `Get-RecoveryLeaseVerdict()` validates token against registry.
- `evaluate_recovery_lease()` reordered: identity check before producer check.

### P0-2: Process-owner verification (FIXED)
- Python engine: `validate_lease_producer_authority()` rejects empty `windows_user`.
- PowerShell: `Get-RecoveryLeaseVerdict()` and `Invoke-ProvenKill()` require
  non-empty `windows_user`; `Get-ProcessOwnerName()` uses CIM instance-method
  (Get-CimInstance + Invoke-CimMethod) instead of class-level call.

### P0-3: Thread-safe lease writes (FIXED)
- `write_lease_atomic()` temp filename now includes thread ID + random nonce.
- Generation-checked optimistic concurrency via `expect_generation` param.

### P1-3: Production managed-worker caller (INTEGRATED)
- New `Scripts/saispin_managed.py`: production caller for SAITULS worker scripts.
- `register_self()`, `authorize_self()`, `heartbeat()`, `revoke_self()`,
  `unregister_self()` wrappers around the engine's lease API.
- Added `now_iso()` to engine for timestamp generation.

### P1-4: Controlled kill acceptance (EVIDENCED)
- Positive: stale authorized lease with stale heartbeat KILLs.
- Negative 1: forged lease (foreign producer_token) REFUSES.
- Negative 2: empty windows_user REFUSES.
- Negative 3: active work (fresh progress) REFUSES.
- Negative 4: revoked ownership REFUSES.

### Test results: ALL PASS (0 failures)
- `python -B tests/test_saispin.py` -- 0 failures
- `--self-test` P1-4 cases added to PowerShell self-test suite.

### Remaining (board-blocked, cannot mutate)
- P1-6 SAIPEN reconciliation: BOARD conflict blocks all mutations.
  Directive P1-6 fallback applied: source work + evidence retained,
  refusal recorded, transition left BLOCKED.
---
