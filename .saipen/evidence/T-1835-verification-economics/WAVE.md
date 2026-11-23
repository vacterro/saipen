# Verification economics — T-1835

WHAT CHANGED: `tools/saipen_metrics.py --verification [--project-root PATH]
[--since YYYY-MM-DD] [--json]` exposes a read-only view of existing full/focused
execution records and consumer observations. It reports sample coverage,
record-wall versus module-process versus consumer-request time, known cache
hits, feedback median/P95, full-run frequency, source generations, repeat
candidates, recorded red IDs and per-ticket measured requests. Text uses the
requested IMPLEMENTATION / FOCUSED TESTS / IMPACT TESTS / FULL TESTS /
WAIT/RECOVERY / OTHER categories. JSON retains the detailed measurements.

WHY THE VIEW WAS MISSING: the existing metrics reporter primarily observes Git
and LOG, while telemetry's phase durations have minute precision and the
efficiency KPI is explicitly approximate. None can prove actual active editing
time. Historical execution records had no consumer attribution or lock wait
measurements. Repeated source fingerprints alone do not prove a redundant run.

The existing request observation gains optional `ticket` and actual monotonic
`coordination_wait_wall_s` fields, including timed-out waiters. Both existing
execution producers supply the consumer ticket. These fields never enter the
compatibility identity, execution lease, verdict, source gate or lifecycle.
No independent store or controller was added. The reporting dependency is
one-way: the metrics CLI imports the helper; engine code never imports it.

MEASURED COST: a direct collection of the live 2026-10-20 window (21 execution
records and 13 requests then present) took 0.175999 s. This is collection wall
time, not end-to-end CLI time, test speedup, human waiting or verification share.
`scan-measurement.json` and `before-live-request.json` preserve that observation.

Missing development/operator elapsed time, typed impact executions, actual
recovery time, provably redundant-run rate and earlier-tier escape attribution
remain UNKNOWN with reasons. Partial stage/module samples report their coverage;
legacy compatibility is not invented. A fresh forced rerun may be legitimate.
Summed concurrent consumer/module durations never become operator waiting time.

REGRESSION CONTROLS: seventeen initial cases passed Windows and Linux before the
canonical package. They exercise shared-record accounting, real measured lock
waiting, actual focused producer attribution, incompatible/legacy evidence,
failures, missing/invalid measurements, date filtering, nearest-rank P95,
read-only reporter behavior and explicit unknowns. Existing real full-CLI
three-consumer controls now also assert that each request carries its own
ticket; their execution and the legacy metrics/source contracts are in the
canonical scoped package. No existing assertion or baseline was removed.

The first canonical package passed 107 tests. Self-audit then found that a
valid JSON FAIL record with missing red inventory printed an empty ID list.
The correction preserves UNKNOWN and explicit inventory coverage, while keeping
all known IDs from partial data. The same final targeted oracle fails on saved
prefix reporter bytes and passes current bytes (`red-inventory-pair.json`).
Final eighteen controls pass Windows/Linux. Current managed-runtime record
`1784abc970cf3401-20261020T171853299982Z.json` was independently reused in REVIEW
in 6.250 s after its first request of 81.281 s. The earlier 107-check package
remains evidence for unchanged producer/legacy/source components.

A live read after actual requests attributed T-1835's two measured consumer
requests to one execution record; implementation time and verification share
remained null. `after-live-request.json` preserves this observation. The final
post-closure view also identifies the ticket as canonically completed.

REMAINING RISK: the view observes stored records and is not current conformance,
acceptance or publication evidence. It cannot reconstruct measurements that
were never captured. The impact producer, CI parity, full stable-generation
acceptance and complete campaign reports remain separate requirements.
Rollback removes this wave's additive CLI/report files and observation metadata
while preserving the previously reviewed C-009 execution/ownership semantics.

This wave completed locally in pending C-010 at E-16746, preserving earlier
cohorts and the full publication boundary. NEXT ACTION: resumed T-1829 SCOUT,
remaining impact/tier/CI/final acceptance requirements; no campaign closure.
