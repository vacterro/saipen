# T-1283 current-tree VERIFY

This is evidence-only completion of the implementation carried by 78447758 and the settled-index sequencing repair in DONE T-1519. No production, test, fixture, success predicate, or global Git setting changed in this pass.

The full acceptance text is preserved in `.saipen/recovery/board-compaction/T-1283/T-1283-431559f37496f73e4c00bd16.BOARD.md`; the compact live row exposes only its first two criteria to the acceptance parser.

| Criterion | Current witness |
| --- | --- |
| AC-01 | `test_t1519_settled_index`: index validates after every settlement; DONE T-1519 supplies the original sequencing regression. |
| AC-02 | `test_a_snapshot_over_a_valid_index_decodes_no_settled_receipt`: counts decodes rather than time; stale and tampered index controls remain. |
| AC-03 | `test_bounded_lookup_cost_is_constant_in_population`: receipt reads bounded across populations 100/1000/10000; mixed-schema bounded lookup agrees with strict scan. |
| AC-04 | `test_append_below_bound_hashes_no_sealed_receipt_bodies`, `test_append_does_not_rehash_sealed_history`, and legacy append tests preserve bounded tail work. |
| AC-05 | Explicit deep-validation, exact-byte tamper, deleted/duplicated/reordered history and rebuilt-index controls remain reachable. |
| AC-06 | Native original/current regression keeps verifier, fixture and configuration fixed; corruption, foreign-object, stale-locator and out-of-band controls reject their bad subjects. |

`VERIFY-retry.stderr` records 38 tests passed, zero skips. The unchanged native oracle records 12 tests: original 11 errors/1 pass, current 12 passes. `original.json` and `current.json` bind the same verifier `62f42c9aba757080ff896b211173398be9658fdfff5782f948c275e06f153161` to different implementation hashes.

The initial mandatory audit failure is retained in `VERIFY-audit.stdout`: a disposable Git fixture lacked the live root's existing `core.longpaths=true`. That pass was stopped and returned to BUILD. The next VERIFY uses `audit_env.py` solely to pass that same native setting to child Git processes; canonical audit command, cases and predicates are unchanged.

`VERIFY-audit-longpaths.json` records actual exit 0: 12/14 probes passed, no failed or skipped probes; 246/247 mutation controls proven, zero broken. `symlink-restore` and one portable external-identity mutation remain UNPROVEN because Windows returned WinError 1314. `audit_checks.py` explicitly classifies that narrow host capability as nonblocking; this does not satisfy the separate mandatory portable-parity gate on T-1602.

Current declared family: 4896 tests, zero red/new-red, fingerprint `32267b416e4798f7`, record `.saipen/evidence/core-unit/32267b416e4798f7-20261003T201330Z.json`, reused by the canonical evidence writer in this cycle. Exact native counts from T-1316: 4839 PASS, 57 SKIPPED, 0 FAIL/ERROR.

Ruff 0.16.0 with canonical `check tools/ tests/` and `git diff --check` passed. Canonical core validation minted CURRENT_PASS (`receipt-68d64c6a5047`), zero blocking findings, 31 warnings. Graph generation 2026-09-01 is stale and excludes `tools/`; exact current source and coverage fallback were used. Confidence: high for the verified ticket scope; host symlink controls retain their explicit limitation.
