# T-1454 runtime integration scope -- attribution

Base: HEAD d97abdc0 (T-1436). Scope: every product path under `tools/`,
`saipen/`, `bootstrap/`, `extensions/` that differs from HEAD in the working
tree on 2026-09-22 -- 45 modified tracked files and 27 untracked runtime files
the runtime manifest already names. Nothing under `.saipen/`, `future_gate/`,
`.workbuddy-ai/` or `KNOWLEDGE/` enters the source commit.

Attribution method: ticket ids carried by the added lines themselves, then
LOG events since E-7732 naming the file, then the LOG build/verify lines of
the owning Work. Every path below has an owner; no path is unattributed.

## Engine (`tools/saipen_engine/`)

| Path | Owning Work |
|---|---|
| audit_manifest.py | T-1452 |
| automation.py | T-1439 |
| board.py | T-1429 (due-time surface, deferred operator class), T-1302 |
| board_compaction.py | T-1429 |
| cold_recovery.py (new) | T-1446 slice, T-1429 |
| command_effects.py | T-1456 |
| conformance.py | T-1439, T-1440 |
| context.py | T-1446 (autonomy / orientation) |
| debt.py | T-1437 (multi-work linkage) |
| entry.py | T-1458 |
| guard_events.py | T-1457, T-1459 |
| intake.py | T-1437, T-1438, T-1453, T-1455 |
| log.py | T-1444 |
| metadata_repair.py (new) | T-1435 |
| operations.py | T-1429, T-1435, T-1437, T-1446 (goal ingress idempotence) |
| pending_ingress.py | T-1457, T-1459 |
| reconcile.py | T-1435, T-1444, T-1346 |
| release.py | T-1455 |
| remediation.py | T-1435, T-1438, T-1439, T-1441 |
| result.py | T-1437 |
| router.py | T-1446, T-1429, T-1458 |
| runtime_namespace.py (new) | T-1435 |
| subs.py | T-1435 (sub reconcile) |
| supervisor.py (new) | T-1446 (decider slice) |
| watchdog.py (new) | T-1448 |
| worker.py (new) | T-1446 (worker turnover slice) |

## Tools and protocol

| Path | Owning Work |
|---|---|
| tools/saipen.py | T-1429, T-1435, T-1437, T-1446, T-1454, T-1457 |
| tools/audit_checks.py | T-1447, T-1345 |
| tools/autoinject.py | T-1454 |
| tools/continuity_probes.py | T-1361 |
| tools/run_scenarios.py | T-1361, T-1345 |
| tools/validate.py | T-1435, T-1439, T-1441, T-1345, T-1302 |
| tools/validator_fail_sites.json | T-1345 (regenerated inventory) |
| saipen/COMMANDS.md | T-1446, T-1435, T-1437, T-1438, T-1439 |
| saipen/COMMAND_EFFECTS.json | T-1435, T-1438, T-1446 |
| saipen/REGISTRY.json | T-1437, T-1438, T-1435, T-1446 |
| saipen/SOURCES.md | T-1438 |
| bootstrap/inject.ps1, bootstrap/inject.sh | T-1361 |
| extensions/schemas/board.schema.json | T-1429 |
| extensions/schemas/state.schema.json | T-1446 |

## Tests (`tools/`)

| Path | Owning Work |
|---|---|
| test_audit_2026_08_28_all3, test_explicit_claim, test_intent_audit_fixes, test_legacy_lifecycle_compat | T-1346 |
| test_audit_manifest, test_t1452_manifest_authority (new) | T-1452 |
| test_check_inventory | T-1345, T-1447 |
| test_remediation_self_consistency, test_src085_conformance_disposition, test_conformance_repair_boundary (new) | T-1439, T-1441 |
| test_t1412_conformance_truth | T-1440 |
| test_source_receipts, test_refusal_registry (new), test_source_multiwork (new), test_user_wait_release (new) | T-1437 |
| test_source_quarantine_route (new) | T-1438 |
| test_metadata_repair, test_producer_terminal_consistency, test_runtime_namespace (new) | T-1435 |
| test_verify_scope_isolation (new) | T-1444 |
| test_cold_recovery, test_supervisor, test_worker_turnover (new) | T-1446 |
| test_watchdog (new) | T-1448 |
| test_t1429_deferred_due (new) | T-1429 |
| test_t1453_ingress_clause (new) | T-1453 |
| test_t1454_distribution_blocker (new) | T-1454 |
| test_source_refusal_routing (new) | T-1455 |
| test_vocabulary_parity (new) | T-1456 |
| test_t1457_ingress_obligation (new) | T-1457, T-1459 |
| test_t1458_queue_reservation (new) | T-1458 |

## Open Work whose bytes ride this commit

- T-1446 (DOING, parked on T-1454): supervisor decider, worker turnover
  harness, cold recovery, autonomy diagnostic. Verified slices (E-7965..E-7969),
  not a closure claim: the resident execution owner, chaos gate and soak are
  still owed.
- T-1429 (TODO): clauses 1-2 verified (E-8114); clause 3 waits for the
  T-1426 live use behind T-1428 -> T-1446.

## Pre-commit gates (2026-09-22)

- runtime cohort (31 test modules in scope): Ran 606 tests OK (174 s)
- ruff 0.16.0 on the 63 changed Python paths: All checks passed
- validate --gate core: 27 problems, all `runtime manifest names a file git
  does not track` -- the class this commit clears
