# T-1361 verification record (2026-09-21)

Ticket verify clause, part 1: `python tools/run_scenarios.py` exits 0.
Ticket verify clause, part 2: every baseline failure identity is closed by a
recorded fixture-staleness reason or an engine fix with its own red control.

## Full integration measurement (ACCEPTED RUN)

- command: `python tools/run_scenarios.py`
- cwd: repository root
- HEAD: `d97abdc097db432bafe2316b1e3577e44cd9cc4c`
- `tools/run_scenarios.py` sha256:
  `70957fdecc49d9c34bce5bb85183160e25602be0589a59ecc7c1a37bcfbad3d3`
- environment: host-session carriers stripped by the harness
  (`session_carrier_isolation`, E-7692); user config redirected to a temp dir
- dirty tree at run time: 701 porcelain lines,
  `status_sha256: a37f2003d1eb1d88decbc4297223bd7408c4e94ef1542d477d28e2075e298622`
- start: 2026-09-21T17:08:43Z, elapsed 1228.75 s, exit code 0
- console: `full-20260921-200843/console.txt` (complete stdout/stderr)
- metadata: `full-20260921-200843/result.json`
- summary line: `All executable scenarios and injector probes passed.`
  `44 of 44 probe group(s) reached a verdict; 1248 grouped check(s) executed`
- concrete FAILED identity set: EMPTY

### Comparison against the preserved baseline, by ID

Baseline capture: 2026-09-21 remeasurement, 88 FAILED identities
(`CLASSIFICATION.md`, `failure-identities.json`, 87 mapped records,
`run-console.txt`).

- disappeared identities: all 88 (0 survivors in the accepted run)
- surviving identities: none
- new identities: none

## Root disposition map (red evidence -> green evidence)

| root | class | red evidence | green evidence |
|---|---|---|---|
| A injector shell/PS byte preservation | ENGINE_DEFECT | `focused-20260921-180125` 6/2, `-180602` 6/1 | `-182723` 6/0 |
| B scheduler uninstall fixture | FIXTURE_STALE | `-180125` 60/1 | `-182723` 60/0 |
| C hostile BOARD fixture | FIXTURE_STALE | `-180020` 17/1 | `-182723` 17/0 |
| D continuity H26/H12 | ENGINE_DEFECT + ORACLE_STALE | `-180020` 1/1 | `-182723` 1/0 |
| E release-executor scope order | FIXTURE_STALE | `-180144` 96/35, `-183412` 96/17 | `-192953` 96/0 |
| F release-relevance continuation gate | ENGINE_DEFECT | `-190601` 96/3 | `-192953` 96/0 + `test_t1405_continuation_scope_stays_trusted_when_reviewed_head_is_an_ancestor` |
| G release-freshness copied board | FIXTURE_STALE | `-194231` 11/4 | `-200427` 11/0 |
| H validator pathspec length | ENGINE_DEFECT | `-195257` 11/3 | `-200427` 11/0 |
| HOME-root / project-root / last-event / scenario fixtures / improve / nitro-integrity / carrier isolation | DIRTY_SOURCE_DEPENDENT, FIXTURE_STALE | baseline B001-B033, B076-B087 | `-180020`, `-180204`, `-180125`, accepted full run |

Baseline records B001-B016, B020-B033, B076-B087 are DIRTY_SOURCE_DEPENDENT:
the copied HOME validator inherited root handoff files and the uncommitted
protocol surface. The handoffs were preserved byte-identically under
`T-1440-incoming-root-handoffs-20260921`; the accepted full run proves the
residual class is closed on current bytes without a commit.

## Instrument controls (VERIFY-ORACLE-01)

- The full-suite gate CAN fail on current lineage: the remeasurement captures
  before the fixes recorded 88 FAILED identities, and each root above has its
  own focused red run before its fix (table).
- No zero-collection run: 44/44 probe groups reached a verdict, 1248 grouped
  checks executed.
- New regression controls: `test_t1405_continuation_scope_stays_trusted_when_reviewed_head_is_an_ancestor`
  (green) with its in-test tampered-byte negative control; the pre-existing
  stale-scope, tampered-hash, missing-scope and foreign-scope controls stay
  green (6/6 focused selection).
- BOARD grammar negative control stays green:
  `tools.test_t1304_review_p0_repair` 25/25 OK, including
  `test_out_of_band_separator_bytes_fail_validation`.

## Known limitations (honest disclosure)

- `tools.test_source_receipts` run as a bare module shows 5 pre-existing
  `PROJECT_LINEAGE_MISMATCH` CLI-subprocess reds caused by the ambient
  host-session carrier; the same module runs isolated inside the accepted
  full suite (`source-receipt behavior(s) executed` group green). This is the
  T-1434 carrier class, not a T-1361 regression.
- No commit, push, tag or publication was performed. The uncommitted protocol
  surface documented in `RECOVERY-E7838-20260921.md` remains the tree's state.