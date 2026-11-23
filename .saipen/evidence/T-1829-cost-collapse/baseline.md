# Historical verification baseline

historical records plus direct filesystem inventory; no benchmark executed

- Full execution records: 554
- Aggregate recorded run wall time: 179.533 h (sum, not operator elapsed)
- Median / P95 run: 1085.0500000000002 / 1806.2 s
- Distinct tested source fingerprints: 453
- Extra same-fingerprint executions: 101
- Extra same-fingerprint PASS executions: 42
- Their recorded run time: 11.919 h
- Records with environment identity / stage timing: 0 / 0
- .saipen inventory: 85509 files, 1354.547 MiB
- Top-level test modules: 456

Same source alone cannot prove environmental compatibility. Duplicates are investigation candidates.
Historical module totals below are summed process time, not parallel wall time.

| Module | Samples | Median process s | Sum process s |
|---|---:|---:|---:|
| test_t1505_core_unit_sandbox_reclaim | 484 | 141.8 | 81881.1 |
| test_t1613_publication_convergence | 257 | 233.5 | 61173.7 |
| test_t1326_board_compaction | 515 | 113.8 | 59368.3 |
| test_t1363_zero_manual_entry | 515 | 112.5 | 59008.0 |
| test_conformance_lineage | 515 | 108.7 | 56117.0 |
| test_t1553_mid_session_activation | 402 | 140.8 | 53187.8 |
| test_t1411_stale_complete_resolution | 515 | 94.3 | 50453.6 |
| test_source_receipts | 515 | 85.2 | 47928.7 |
| test_t1461_source_append | 515 | 92.1 | 47744.2 |
| test_t1474_start_goal_entry | 515 | 107.9 | 46493.4 |
| test_opencode_host_smoke | 515 | 82.6 | 45210.3 |
| test_t1412_conformance_truth | 515 | 83.7 | 44767.9 |
| test_entry_point_parity | 515 | 82.5 | 43765.9 |
| test_t1501_entry_resolver | 494 | 82.95 | 41724.7 |
| test_recovery_reachability | 515 | 76.7 | 40465.0 |

## Missing observations

No historical stage timers or environment identity exist in these records. Copy/hash/discovery/startup/validation/gate wall time, fresh-run cause, implementation time, flake attribution and true verification share are unknown, never zero.
The operator's 98% observation remains unverified. No throughput target is claimed achieved.

## Ranked mechanisms to investigate

1. Repeated full executions / per-ticket boundary frequency: candidate upper bound is the repeated PASS hours above; compatibility must be proven before savings are claimed.
2. Whole-family execution for narrow iterations: prior focused work changes scope; its timings are not an equivalent-workload speedup. Inspect formal lifecycle safety before treating it as sufficient.
3. Serial full runs versus existing shards: historical job distributions are available, but workload/host/environment equivalence is not proved.
4. High-cost modules above: profile mechanism before editing assertions or fixtures.
5. Full .saipen copies, repeated shard copies, source hashes and discovery: large inventory is observed; duration and preventable share still need direct timers.
6. Repeated lifecycle/status gates: existing KPI is not elapsed time. Instrument one representative gate before generalizing.

## Dependency evidence

MCP graph/coverage tools are unavailable in this host. dependency-evidence.json records exact static source fallback and limitations; dynamic completeness is not claimed.
