# T-2111 — performance refresh, post-T-2109 bytes (2026-11-20)

Scope: "continue optimizing SAIPEN without harm to logic and efficiency"
(SRC-434). Method: premise-check first, then measurement; no source change
without a new RED. Companion facts: T-2108 BASELINE (`../T-2108-performance-
baseline/BASELINE.json`, measured O0–O7 saturation) and knowledge card
`a-full-snapshot-is-not-an-optimization-on-a-settled-journal`.

## 1. Premise checks (candidates closed by settled evidence, not re-run)

1. Canonical-validator repetition per `cc`: **already bounded** —
   "ONE revalidation per cc (`budget`)" (`tools/saipen.py`, `_auto_doctor`
   docstring, T-1792/SRC-253/T-1818); T-2109 added the host wall-clock DEFERRED
   (demonstrated: 60s reverify stub → `_next_action` returns in 0.008s with
   `doctor.stage=DEFERRED`, E-21972). Re-opening it would weaken a control,
   not optimize.
2. Service hotspots (identity calls, TOCTOU path proofs, intake reads,
   snapshot): falsified by T-2108 O-waves — mandatory controls or measured
   worse (shared snapshot 5.02s vs bounded 0.60s). No premise changed since.
3. Core-unit family runtime (2729s): evidence discipline, not a user-facing
   service; parallel/shard tampering risks oracle determinism — out of
   bounds under "no harm to logic".

## 2. Fresh measurements (this session, warm box, ±2% stability, n=4)

| Surface | p50 | Note |
|---|---|---|
| `python tools/saipen.py status --json` (repo 8.1.1) | **5.1s** | 4951/5115/5127/5103 ms |
| `python tools/saipen.py status --view agent --json` (repo) | **5.0s** | 4922/5047/5073/4697 ms |
| `saipen status --json` (PATH → AppData 8.1.0) | **10.7s** | 13334/10805/10287/10588 ms |
| `status --view agent` output size | **31747 B ≤ 32 KiB** | bounded, 1021 B margin (32768-31747) at current BOARD size |
| `python -B tools/perf_wave_regressions.py` | **42/42 PASS, 0 failed** | same verdict as T-2108 rerun2 |

- The installed 8.1.0 PATH engine is **2.1× slower** than the repo engine on
  the same box right now; the release/installation gap remains the dominant
  measurable performance cost. Its cure is the ONE operator decision
  (install mechanism; see `../T-2110-nightshift-drift/DRIFT.md` §4).
- Same-day absolute walls are environment-sensitive: T-2108's morning
  repo-full 10.53s (n=3, 05:23) did not reproduce now (5.1s, warm). Rank
  engines intrinsically only via same-condition pairings — as T-2108 did —
  never across sessions.
- Growth note (no defect today, T-2090/T-2091 own the class): agent-view
  has only only 32768-31747 = 1021 B of margin before the 32 KiB bound must engage; their
  truncation-flag/tail-digest behavior was green in the 8828-test family of
  20.11 14:33 (not in the new_red set).

## 3. Verdict

No safe source-level optimization candidate exists on these bytes: the wave
is green, the surfaces are stable and bounded, the settled controls stay
untouched, and every remaining performance item (T-2090/T-2091 closure,
ZAICODE ~200k compaction + sidebar re-render regressions, and the 8.1.0 →
8.1.1 runtime gap itself) is parked behind the shared-tree foreign-red SHIP
gate and the operator release decision, not behind missing code. The 12
foreign reds (T-2049 `gc` WIP, T-2066 staged host policy, stale fixtures)
and the install authority are the two levers; both are recorded with exact
owners in DRIFT.md §4–§5 and LIVE_STOP_MATRIX §11.
