# Campaign acceptance audit — T-1829 / SRC-285

This is a requirement-to-evidence inventory, not a PASS certificate. It retains
the entire mission in SRC-285, sections 4–16. Local DONE wave tickets and scoped
PASS records do not close this parent or authorize publication. Current
STATE/BOARD/LOG and immutable execution records outrank this document.

Audit basis: the current source, source contracts/coverage, named wave reports,
the final 177-control record below, saved unchanged-oracle RED/GREEN pairs and
actual Windows/Linux logs were inspected. MCP graph/coverage tools are absent;
source fallback is explicit in dependency-evidence.json. Static discovery is
not proof of complete dynamic dependencies. No second-agent review is claimed.

## Historical and measured cost, section 4 A–N

| Item | Available evidence | Limit / acceptance consequence |
|---|---|---|
| A Full-suite count | baseline.json: 554 full core-unit records | Named family count; not 554 executions of every canonical family |
| B Aggregate/median | baseline.md: 179.533 summed recorded hours; median 1085.05 s, P95 1806.2 s | Sum is not elapsed operator time |
| C Family costs | Existing full/focused records and verification_metrics.py | Legacy data predominantly covers core-unit; missing family histories remain unknown |
| D Module costs | baseline.md and baseline.json module-duration samples | Summed process time, host/load varies |
| E Repeated fingerprints | 101 extra executions, including 42 extra PASS records / 11.919 recorded hours | Historical environment equivalence unavailable; candidate savings, not proven wasted hours |
| F Fresh non-reusable runs | New verification identity/observations; legacy records lack causes | Fresh request is not automatically redundant; unknown historical causes retained |
| G Copies | T-1831 before/after; current scoped timers; sandbox-paired-20261020.json | Whole-state experiment is a copy observation, never suite acceptance |
| H Hashing | Final 177-control record: 0.141 s hash stage | One direct Windows observation, no general distribution |
| I Discovery | Sandbox reports and shard discovery_process_s | Process-summed discovery is distinct from wall time; exact inventory digest retained |
| J Process launch | test_runner._run_family process_create_s and real owner controls | Measures creation only, not all interpreter/import startup; missing legacy samples unknown |
| K Canonical validation | T-1839 validation-timing.json / validation-after-index-timing.json: 34.008 s with 13 problems, 28.492 s after exact tracking repair with one remaining EX problem | Different inputs, no performance comparison; no green canonical gate claimed |
| L Repeated lifecycle gates | Real first/reuse request pairs, independent citations | Request wall includes coordination/identity/gate work; no invented decomposition |
| M Retry/timeout/flake loss | Existing verdicts/timeout records; new red inventories | A failure is not proof of a flake; historical retry causality unknown |
| N Execution versus implementation | Read-only reporter explicitly returns unknown active development/share | Operator's 98%, 30% campaign and 15% stretch shares are not measured achievements |

## Sixteen adversarial controls, section 15

Test locations are precise executable witnesses. Existing results apply to
their recorded generations and platforms. A whole final-generation package and
independent remaining families/platform/install/release gates are still due.

| # | Requirement | Concrete controls / existing evidence | Audit disposition |
|---|---|---|---|
| 1 | Compatible callers share one execution | test_t1832_single_flight.RealConcurrentCliTests: three callers, one actual probe line, one record, two shared consumers; both ordinary and concurrent fresh forms | Scoped executed; concurrent-pair.json preserves same-oracle old FAIL/current PASS |
| 2 | Relevant source change rejects old PASS | test_t1828_verification_policy.test_changed_tree_refuses_focused_evidence; test_core_unit_gate current-tree controls | Scoped executed; final full-generation acceptance due |
| 3 | Configuration/environment/runtime changes reject evidence | T-1832 CompatibilityTests environment, interpreter, profile, tool-content controls; T-1834 semantic environment negative control | Scoped executed; actual managed-runtime identity retained |
| 4 | Failed run never becomes PASS | T-1832 latest-compatible-red, cached-failure and real three-consumer-failure controls | Scoped executed; all consumers retain FAIL |
| 5 | Interrupted ownership recovers | T-1832 FlightRecoveryTests and T-1833 PosixVerificationOwner, real owner death before/after registration, descendant reaping and orphan recovery | Windows applicable subset plus actual Linux execution; Windows skips are not Linux PASS evidence |
| 6 | Parallel consumers receive immutable correct verdict | T-1832 actual concurrent PASS/FAIL; incompatible request bound; record digest/scope tamper controls | Scoped executed; execution and consumer attribution distinct |
| 7 | Narrow result cannot impersonate full | T-1836 forged-full/configuration tests; T-1828 publication gate; shared full-scope predicate | Scoped executed; scope-pair.json old predicate FAIL/current PASS; no raw-Git enforcement claim |
| 8 | Shared dependencies select broader coverage | T-1836 transitive consumers, package initializers, shared fixtures and protocol/adapter/validator boundaries | Scoped executed; actual SAIPEN graph currently escalates FULL |
| 9 | Unknown dependencies escalate | T-1836 reflection/dynamic/file/alias/callback/missing-Git/deletion/uncovered-consumer controls | Scoped executed; no dependency-completeness or automatic narrowing claim for SAIPEN |
| 10 | New tests cannot disappear | T-1830 new-test/import-failure/exact occurrence controls; T-1836 real Git-added tests; T-1837 imported TestCase/empty-partition controls | Scoped executed; whole discovery observation has exact inventory, not count-only proof |
| 11 | SHIP/publication safety remains effective | T-1828 release-before-validator rejection, current-full and new-red publication controls; T-1836 relabelled-scope rejection; core_unit/focused_unit publication predicates | Scoped gates executed; actual final batch/provenance/binding ship gate still due |
| 12 | Injected runtime matches source behavior | T-1837 ActualCliTests.test_installed_engine_uses_same_interface_from_an_unrelated_directory copies actual tool/package and executes its family CLI | Bounded copied-engine acceptance only; complete injector/install acceptance and stale EX-000010 closure remain due |
| 13 | Windows/Linux no hidden bypass | Actual Linux T-1832/T-1833 owner tests; Ubuntu T-1835/T-1836/T-1837 logs; same-scope 46-control concurrency samples on both hosts | Bounded platform evidence; final whole-family/platform/portable-floor acceptance due |
| 14 | Failure reporting stays visible | test_runner_failure_roster; T-1837 actual red/error/import-failure names and causes, inherited baseline not consulted in CI | Scoped executed; no baseline growth or hidden red allowed |
| 15 | Stale/forged/incomplete/mismatch fails closed | T-1832 receipt/scope tampering; T-1836 stale plan/manifest/full-label; T-1830 equal-count omission/duplication; T-1837 missing/mismatched/empty-whole/timeout | Scoped executed; immutable record hashes remain authoritative |
| 16 | Instrumentation measures real observations | T-1830 real copy/serial/shard timers; T-1835 invalid/missing timing, partial failure inventory, nearest-rank P95, shared-record and read-only controls | Scoped executed; absent implementation/share/escape observations remain unknown |

## Last complete reviewed aggregate before T-1839 changes

The final reviewed focused record is
`../focused-unit/d23c49152ef1f81d-20261020T184050402278Z.json`, SHA256
`d1b0f75f724b65a36d93e5e0f4aaacb85db9ab082e143527238f0c63f055e098`.
It reports 177 tests, PASS, 248.875 s. Its thirteen patterns cover dispatch,
full/focused/impact gates, membership, cleanup/process ownership, single-flight,
failure rosters and command/refusal/UTF-8 contracts. It does not cover every
campaign test: for example T-1831/T-1833/T-1834/T-1835 have separate earlier
recorded executions. Those are not silently treated as a current aggregate.
The native Linux logs execute platform-specific owner controls that Windows
skips. No addition of these counts is presented as unique final-suite coverage.
T-1839 subsequently changed source. Its WAVE.md records bounded new controls;
no complete current-generation aggregate replaces the older record yet.

RED/GREEN pairs additionally inspected: T-1832 concurrent-pair.json;
T-1833-owner-guard/regression-pair.json; T-1834-tool-call-identity/regression-pair.json;
T-1835-verification-economics/red-inventory-pair.json;
T-1836-impact/scope-pair.json; T-1837-ci-parity/oracle-pair.json. Their before
subjects are the explicitly saved controlled subjects, not invented historic
whole checkouts. Oracle digests agree within each pair.

## Final gate order and incomplete requirements

1. Paired full-state observations and the bounded decision are recorded in
   SANDBOX.md and sandbox-pair-audit-20261020.json. Exact byte equality is proved
   independently; unfinished native later stages are not PASS. Retain durable
   evidence, snapshot consistency and private mutable workers; no hardlinks.
2. Complete final batch attribution/metadata before freezing the subject.
   C-007/C-008 contain earlier shared-file generations; C-009 through C-012
   preserve later local reviewed waves. Never rewrite historic member hashes.
   The exact audit is cohort-audit-20261020.json; canonical C-007 dry-run refuses
   STALE_PLAN. T-1839 owns lossless reviewed cumulative-batch reconciliation.
   T-1839 and T-1840 are now locally DONE in pending C-014/C-013. Current
   EX-000014 and canonical core CURRENT_PASS restore truthful external proof;
   the final integrated target and actual reconciliation still remain due.
3. Measure one canonical validation and collect strongest remaining cheap
   static/lint/import/schema checks. A mandatory failure stops the PASS path
   and is repaired at its owner before another unchanged expensive run.
   The observed full pinned Ruff gate has 210 inherited findings in 20 files;
   T-1841 owns that repair before the final expensive campaign checks.
4. Run one full core-unit family on the final stable generation using the
   existing evidence producer. Account for all expected occurrences, skips,
   import errors, baseline and exact source/runtime/configuration. Preserve
   failures; never expand the baseline to make the campaign green.
5. Run the independently declared consumer-unit, validator, audit-checks,
   scenarios, audit-floor, audit-parity, audit-order, audit-tags, Ruff and
   portable-floor families. A full unit record proves none of these by itself.
   Complete actual platform/injected-layout/security/distribution obligations.
6. Verify publication provenance, source clause dispositions and A–J delivery
   against final records. Only then may parent VERIFY/REVIEW/SHIP close. GitLab
   is the configured destination, not an existing publication receipt.

The 30%/15% shares need measured development intervals and an observed workload;
they cannot be certified from a focused speedup. Missing observations remain
reported debt. No hand edit to STATE, BOARD, LOG or Source coverage is permitted.
