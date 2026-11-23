# Test execution cost collapse — delivery and remaining work

T-1829 / complete mission SRC-285. This is the current delivery inventory;
the campaign is active, final acceptance and publication are not achieved.

## A. Verified causes and B. historical baseline

baseline.md/json record 554 full core-unit executions, 179.533 summed run-hours,
453 source fingerprints and 42 extra same-fingerprint PASS runs representing
11.919 recorded hours. Environment/configuration compatibility was not captured
historically, so those hours are candidate repeated cost rather than proven
unnecessary execution. dependency-evidence.json records source fallback and its
dynamic-coverage limitation. The operator's approximately 98% share is not a
measured process statistic.

Direct mechanisms established by executed controls and source inspection:

* The cleanup acceptance fixture copied the whole live repository for a small
  cleanup/ownership contract, twice; copying/cleanup dominated actual execution.
* Source-only historical identity could not establish environment equivalence.
  Independent authorized callers lacked one per-identity execution barrier.
* POSIX reader registration and owner death needed a launch boundary that
  prevents execution before ownership is registered and reaps descendants.
* Diagnostic host carriers changed otherwise equivalent child environments.
* Count-only shard merging could hide one omitted and one duplicate occurrence.
  Imported TestCases also create legitimately empty planned workers that differ
  in raw exit behavior between Python 3.11 and 3.12.
* Whole-family validation at every local ticket boundary repeated publication
  cost during ordinary edits. The existing opt-in focused/cohort policy retains
  full final-batch publication protection; TIER-CONTRACTS.md audits that boundary.
* Eager impact analysis kept scanning after a mandatory FULL decision was known.
* CI/family CLI used a separate dispatch path with an extra outer copy. It now
  consumes the existing immutable full-unit engine and preserves strict CI red.

## C. Ranked expensive mechanisms and D. implemented waves

Ranking separates measured savings from possible savings. Details and per-wave
change/cause/savings/regression/risk/next action remain in CAMPAIGN.md and each
named WAVE.md; ACCEPTANCE.md maps every required adversarial control.

| Priority | Mechanism / implementation | Measured result | Remaining exposure |
|---|---|---|---|
| 1 | Repeated full execution; T-1832 single-flight, T-1833 ownership, T-1834 identity | Three actual compatible CLI consumers execute one probe and receive one record; final 93-control first request 185.859 s / independent reuse 5.938 s | No assertion that all 11.919 historical candidate hours were avoidable; unknown external environment refuses replay |
| 2 | Full verification at local edit boundaries; existing T-1828 policy, T-1836 scoped contracts | Final 177-control package first request 260.688 s / REVIEW reuse 8.735 s | Focused scope is smaller than full; this is repeat feedback, not equivalent full-suite speedup |
| 3 | Overlarge cleanup fixture; T-1831 | Same host/runtime and unchanged 21-control acceptance: 136.656 s to 6.578 s, 95.2% lower module wall time | Intentional fixture-input reduction; complete suite speedup unmeasured |
| 4 | Pointless dependency scan after FULL is mandatory; T-1836 | Frozen 464-module inventory and same FULL decision: eager 13.741/13.989 s versus early escalation .261/.304 s | Actual SAIPEN domain is not certified for narrowing; no automatic omission |
| 5 | Whole-state and per-worker copies | Current stage observations and paired sandbox report | Required durable state remains copied; hardlinks cannot isolate mutation; no speculative whole-tree exclusion |
| 6 | Worker concurrency and duplicated CI outer copy; T-1837 | Same 46-control corpus: Windows jobs 1/2/4 = 13.256/10.665/11.164 s; Linux = 3.719/2.438/2.606 s | Single samples, reduced corpus, no peak memory/hosted I/O sizing; workflow retains jobs 1 |
| 7 | Missing economic observations; T-1830/T-1835 timers/reporter | Live collection sample .175999 s; actual execution/request/stage scope, latency and cache observations retained | Active development/share/escape attribution unknown; advisory output grants no authority |

## E. Comparison limits and F. regression evidence

Equivalent acceptance comparisons: unchanged 21-control cleanup module on the
same Windows host/runtime; same frozen impact input/inventory/FULL result;
same frozen 46-control concurrency workload per host; independent compatible
consumers reuse the same actual immutable execution. Different test selections,
source generations, hardware or operating systems are never treated as one
before/after full-suite throughput result.

ACCEPTANCE.md lists all sixteen controls, saved unchanged-oracle RED/GREEN pairs,
the exact current 177-control record and uncovered final requirements. Native
Linux ownership tests supplement platform skips; their counts are not fabricated
Windows passes. Final stable-generation full/multi-family acceptance remains due.

## G. Coverage and safety parity

No focused/impact result may become a full record. Full production/cache/reuse,
local full SHIP and publication consume the shared full-scope predicate. CI
rejects every red, including inherited baseline red. Exact ordered inventory
and occurrence coverage reject count-cancelling duplicates/omissions; imports,
fixture order, new tests, raw empty-worker results and causes remain visible.
Private mutable fixtures/workers, canonical snapshot consistency, source
authority and ownership checks remain required. Existing safety assertions,
real-process/platform acceptance, historical member hashes and durable evidence
were not waived by this report. Final acceptance must prove the combined result.

## H. Debt and I. next roadmap

Immediate: paired sandbox conclusion; final batch/provenance and metadata;
canonical validation measurement; one final stable-generation full unit run;
independent canonical families; actual installation/platform/release gates;
Source coverage reconciliation; reviewed canonical closure/publication.

Measured follow-up, without claiming it complete: use current stage observations
to choose the next expensive fixture/module; investigate safe immutable snapshot
sharing only with mutation isolation; consider shared discovery only after a
benefit outweighs manifest/import/fixture semantics risks; size hosted concurrency
using complete state and peak memory; capture development intervals and typed
tier-to-regression observations before estimating the 30%/15% share targets.
Avoid repeating unchanged rejected hardlink/exclusion hypotheses.

## J. Canonical state and next action

Current STATE is BUILD / T-1829, owner saipen-cli. T-1839 and T-1840 are locally
DONE in pending C-014/C-013. T-1830/T-1831/T-1832/
T-1833/T-1834/T-1835/T-1836/T-1837 are locally DONE; pending cohort publication
is distinct. SRC-285 R001–R011 remain UNKNOWN coverage assigned to T-1829.
The current branch has a large inherited mixed worktree/index; no blanket staging
or attribution is authorized. origin is GitLab; github-backup preserves the prior
destination. No campaign commit, tag, push or hosted CI result is claimed.

The sandbox decision is now recorded in SANDBOX.md, including independent exact
Windows/Linux first-copy byte proof and the unfinished Linux later-stage limit.
The cohort audit proves 7/6/5/4/1/0 stale member hashes in C-007 through C-012;
canonical C-007 ship dry-run refused STALE_PLAN without writes. T-1839 implements
the bounded repair, now including strict matching release-cohort identity.
Actual current EX-000014 binds the unchanged original readiness contract and
T-289 carrying commit 041f00ed1bc0b4b4841ca3edbb5912dd39461349; three real
unskipped Windows readiness checks pass, canonical target hashes unchanged,
temporary grant revoked and owned fixture removed. Core is CURRENT_PASS.
Current scoped records report 132 PASS for T-1840 and 105 PASS for T-1839;
their distinct generations/scopes do not constitute final full acceptance.
The full pinned Ruff gate has 210 inherited findings in 20 files; T-1841 owns
their behavior-preserving repair before final generation freeze and expensive
campaign gates. Actual cumulative cohort reconciliation/publication remains due.
Next exact action: complete T-1841, then ACCEPTANCE.md's final gate order.
This report records observed state; it is never execution authority.
