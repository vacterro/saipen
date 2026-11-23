# SRC-396 — FINAL REPORT
Mission: Repair verified release-target, authorization-preview and grant-selection defects without weakening real operator authority. Preserve the completed maintenance policy v2 repair. Unblock independently authorized engineering where possible. Do not confuse a release blocker with maintenance authorization or a missing native host scheduler.

---

**CURRENT_WORK** — T-2027 (SRC-396) completed. 8 paths bound to `66ef622a`: `saipen/REGISTRY.json`, `tools/saipen.py`, `tools/saipen_engine/isolated_release.py`, `tools/saipen_engine/release_authority.py`, `tools/test_isolated_release.py`, `tools/test_release_approval_contract.py`, `tools/test_release_reconciliation.py`, `tools/test_t2027_release_authority_transaction.py`. 20 controls added; 17 pre-existing release-family tests updated to reflect the repaired behaviour.

**RELEASE_DESTINATION** — No single canonical destination is established by this repair. The live tree has two configured remotes with diverged `main` tips:
- `origin` → `https://gitlab.com/vacuum34/saipen.git` @ `60783ac4abb78c06867aa833d692801f8e36b80c`
- `github-backup` → `https://github.com/vacterro/saipen.git` @ `3c96a98926b762547388ebd84708e8e6744e42e5`
Local `HEAD` is `66ef622a43ab59512735ac78ce10d1250e26f9df`. Neither remote is an ancestor of HEAD. The executor no longer defaults to `origin/main`; a publication destination is decided by the operator via `saipen release approve --remote <r> --branch <b>` and is bound to the single active grant.

**ORIGIN_REMOTE_IDENTITY** — `origin`, URL `https://gitlab.com/vacuum34/saipen.git`, push URL same, `refs/heads/main` tip `60783ac4abb78c06867aa833d692801f8e36b80c`.

**GITHUB_REMOTE_IDENTITY** — `github-backup`, URL `https://github.com/vacterro/saipen.git`, push URL same, `refs/heads/main` tip `3c96a98926b762547388ebd84708e8e6744e42e5`.

**ANCESTRY_RECONCILIATION** — `git merge-base --is-ancestor` measured in all four directions: `github-backup/main` is NOT an ancestor of HEAD and vice versa; `origin/main` is NOT an ancestor of HEAD and vice versa. Both lineages have diverged from local HEAD. Integration is an ordinary engineering step the crate supports (`--reconcile-remote-head` names a caller-chosen base; the ancestry gate still runs — `test_p0_05_reconcile_remote_head_is_a_caller_named_tip_not_a_bypass`), but the choice of which history is canonical is the operator's decision.

**ACTUAL_REVIEWED_SCOPE** — The 8 files above. No other changes. The shared index tree `c025cf8dd110c6db351f87496980c3c90c7522ef` was snapshotted before and after the local ship; it is byte-for-byte identical.

**PREVIEW_GRANT_CONSISTENCY** — **TRUE**. Both the operator preview and the persisted grant are built from one `build_release_transaction` dict. Controls: `test_p0_01_displayed_and_granted_destination_always_agree`, `test_p0_01_packet_url_matches_the_granted_url`. Negative control `test_p0_01_explicit_destination_differing_from_the_packet_is_refused` asserts the preview disagrees with the stale packet and the grant follows the preview.

**STALE_PACKET_REFUSAL** — **CONFIRMED**. The historical `approval_packet_20261102.json` returns `RELEASE_DESTINATION_DIVERGED` (`github-backup/main tip 3c96a989... is not an ancestor of the requested base 66ef622a...`). With no destination named, `RELEASE_PROPOSAL_UNAVAILABLE` is returned — no fallback to a historical packet, hardcoded commit, URL or staging hash. Controls: `test_p0_03_no_frozen_base_commit_without_an_authenticated_source`, `test_p0_03_no_frozen_staging_hash_or_path_count_is_presented`, `test_p0_03_the_shown_staging_hash_is_the_live_index`.

**PTY_OPERATOR_SPOOF_REFUSAL** — **CONFIRMED**. `approve_release_command(root, confirm=True, stdin_isatty=True, standing=True)` returns `REFUSED_SYNTHETIC_APPROVAL` ("Operator approval requires genuine human confirmation. Automated model shell invocations cannot synthesize operator authority. (no operator-carried ingress was presented)"). Zero grants persisted. Controls: `test_p0_02_a_supplied_tty_flag_is_not_operator_provenance`, `test_p0_02_confirm_without_any_provenance_is_refused`.

**IMMUTABLE_BASE_BINDING** — **CONFIRMED**. `resolve_commit(root, 'HEAD')` → `66ef622a43ab59512735ac78ce10d1250e26f9df`. The grant stores and matches on this SHA. `test_p1_04_a_symbolic_base_ref_matches_its_commit` passes for both `HEAD` and the SHA; `test_p1_04_an_unrelated_base_ref_does_not_match` proves the match was not widened.

**RELEASE_GRANT_PROOF** — **ZERO**. No grant was minted because no genuine operator-carried ingress was presented. The live refusal above is the proof. An approved grant would be a JSON file under `.saipen/authority/release_grants/` carrying `grant_id`, `base_commit` (the resolved SHA), `target_remote`, `target_branch`, `reviewed_scope_hash`, `protected_staging_hash`, `no_force: true`, and broker-verified provenance fields. The ledger is currently empty.

**FINAL_FULL_GATE** — **PASS**. `tools/core_unit.py evidence T-2027 --agent saipen-cli` → `ok: true, verdict: PASS, ran: 9042, red: 3, new_red: 0, fixed: 0`. The 3 reds are the declared `test_t1816_provenance_inventory` baseline (external drift from an AUDAPACK commit, recorded in `core_unit_baseline.json`). Record: `.saipen/evidence/core-unit/40c4a727b6f1b205-20261105T114017407756Z.json`.

**PUBLICATION_RESULT** — **LOCAL_SHIP_ONLY_PENDING_PUBLICATION**. `saipen ship` refused `VALIDATION_FAILED` on foreign pre-existing staged paths (other Work's paths in this shared tree, byte-unchanged by T-2027). `saipen ship --isolated` was not attempted because no active grant exists and no genuine operator ingress was available. No commit, tag, push, or index mutation was performed. The ticket closes with `publication_state: pending`. A later cohort release (`saipen cohort ship <C-###>`) names T-2027 to flip the state to published.

**REMOTE_VERIFIED_SHA** — **NOT_APPLICABLE**. No push was attempted, so no remote SHA was verified and none is claimed. An unchanged remote tip is not evidence of a successful publication.

**SHARED_INDEX_PRESERVED** — **TRUE**. `isolated_release.snapshot_shared_index` before and after the local ship: `a30d622ab457bfb59a3d375772d999f649f33121060ef6638bd90f6de038c8e0` (1 254 798 entries). `isolated_release.verify_shared_index_unchanged` passed.

**MAINTENANCE_POLICY_V2** — **PRESERVED**. `MAINTENANCE_POLICY_VERSION = 2`, digest `sha256:fdc3d057a55655025d09f4a4dfcffdc7579ba3e54ef38a2cf3af6c8032bef24d`. `goal_authority.active_maintenance_goals` returns `["self-maintenance-core"]`. Control `test_policy_v2_binding_is_untouched` pins the exact digest. The `PROPOSAL_OBJECTIVE_MISMATCH` refusal on re-entry of the historical pivot is preserved (P1-06 / P0-06).

**PERSISTENT_GOAL_APPROVAL** — **NOT_GRANTED**. The `self-maintenance-core` goal remains ACTIVE but has no standing operator authorization. This session's own accidental `saipen goal` call created T-2028/SRC-397 with `witness: model_supplied` — correctly classified as an impersonation hazard (P0-07) and blocked on the operator (E-20629). No model-minted grant exists.

**ZAICODE_NATIVE_SCHEDULER** — **NOT_AVAILABLE**. `saipen host doctor` reports every installed host runtime as `STALE_RUNTIME` (admission `ADVISORY` or `DEGRADED_UNVERIFIED`). Machine runtime `MACHINE_RUNTIME_STALE` (generation `gen-sha256:be78d49b...` ≠ canonical `gen-sha256:625cc2c5...`). No successor-turn transport is registered. The campaign/host dispatch ledger (`.saipen/campaign/`) contains only `authorization_request.json`; the dispatch journal is `JOURNAL_ABSENT` (0 entries).

**REAL_SUCCESSOR_TURNS** — **ZERO**. No `HOST_ACCEPTED`, `TURN_STARTED`, `TURN_COMPLETED` broker receipts exist for this project in the current run. The `installed_host_acceptance` fixtures are mocks; live installed-host acceptance is not claimed (every installed runtime is `STALE_RUNTIME`).

**TRUE_STOP_REASON** — **OPERATOR_AUTHORITY_AND_HOST_CAPABILITY_MISSING**. The release path is blocked because (1) no genuine operator-carried ingress exists to mint a release grant, and (2) both remote lineages have diverged from HEAD — the operator must choose which history is canonical and authorize the integration. The maintenance path is blocked because the persistent goal has no standing operator authorization and no native ZAICODE scheduler exists to run autonomous turns. Neither blocker is repairable by SAIPEN unit tests.

**ONE_GENUINE_OPERATOR_ACTION** — **NONE_TAKEN**. No operator-carried ingress was presented during this session. The single `saipen goal` invocation was `model_supplied` and correctly blocked.

**NEXT_AUTOMATIC_ACTION** — **saipen continue**. T-2027 is DONE, SRC-396 is closed. The remaining BLOCKED tickets are pre-existing and require their own operator decisions or external resources. No new actionable Work is in DOING.

---

Evidence records:
- SCOUT: `.saipen/evidence/T-2027-release-authority-scout.md`
- Live refusals: `.saipen/evidence/T-2027-live-refusals-and-pending-publication.md`
- Focused gate: `.saipen/evidence/focused-unit/40c4a727b6f1b205-20261105T102936632876Z.json`
- Full gate: `.saipen/evidence/core-unit/40c4a727b6f1b205-20261105T114017407756Z.json`
- Release scope: `.saipen/kitchen/release_scope/T-2027.json`
- LOG events: E-20619 (SCOUT), E-20623 (VERIFY), E-20628 (full PASS), E-20630 (verify checkpoint), E-20631 (REVIEW), E-20634 (review checkpoint), E-20635 (SHIP), E-20636 (scope), E-20637 (ship checkpoint), E-20638 (ticket DONE + SRC-396 closed)

Protocol: no force push, no index mutation, no commit/tag/push, no model-created operator approval, no declaration of autonomous maintenance readiness without a running scheduler, no claim that an unchanged remote SHA is a successful publication.