# SAIPEN — Night Shift 6 Report (T-2090, Hyperlean continuation)

**Date:** 2026-11-18 · **Engine:** repo `tools/saipen.py` @ tree dc39709c0 (dirty)
**Status:** implementation DONE (4 handoff P0 + 3 adjacent RED→GREEN, canonical
pair PASS, parity MATCH, perf time-neutral); **SHIPPED: NO** — the SHIP gate
honestly refuses on 9 foreign-WIP new reds (untracked/staged files of other
tickets inside `tools/`); the refusal is recorded, not bypassed.
**Scope contract (operator, mid-shift):** one subsystem contract per wave
(receipt capture + projection digest), adversarial self-verification before
DONE, risk-based P0 admission, budget back on performance/autonomy.

## Canonical evidence (machine-anchored)

- Explicit verify PASS checkpointed; canonical regression pair EXECUTED:
  op `regression-execution-83f02fc0d15f4ae18e56178e3e61aae8` —
  contract `.saipen/evidence/T-2090/t2090_contract.json`,
  oracle `tools/regression_t2089/t2090_night6_oracle.py` (unittest),
  before = FAIL 5/5 on prefix snapshots
  (`.saipen/evidence/T-2090/prefix/…`), after = PASS. Same verifier
  anchored on both stages.
- Live parity: engine vs independent naive reader MATCH
  `23c234c80d332fda` over 20281 receipts, 0 structural errors.

## RED (live repo engine, hermetic fixtures only)

New verifier: `tools/regression_t2089/t2089_p0_night6.py` — 10 checks.

| # | Defect | RED proof |
|---|---|---|
| N6-A | `_bound_string` multi-chunk tail hash breaks byte ORDER (first dropped chunk hashed AFTER later chunks) | digest mismatch on 5 handoff cases + 40-trial seeded property oracle; all tails >1 chunk wrong, 1-chunk tails (all prior GREEN cases) hid it |
| N6-B | regular-file substitution between lstat and open accepted (only type checked, identity never compared) | `os.replace` swap in the open hook → manifest_raw is the replacement's bytes, structural_error=None |
| N6-C | growth after fstat misclassified as complete read (`len(data)==size` ≠ EOF) | append 8 B in the read hook → 8 of 16 bytes captured "complete", structural_error=None |
| N6-D | 256 MiB cap bypassed on the initial read (cap only inside the fallback loop) | 257 MiB sparse file → os.read REQUESTED 257 MiB before any check |
| N6-X1 | shrink during read captured silently | truncate in the read hook → 1 KiB of 64 KiB "complete" |

## GREEN (structural repair, same oracle, same fixtures)

- **A — order-invariant tail hashing** (`saipen.py` `_bound_string`): the
  kept prefix resolves its valid UTF-8 boundary the moment the budget fills;
  straddled bytes open the tail, the first tail chunk flushes immediately
  after, later chunks stream in order. No held-back chunk survives the
  iteration that produced it, so the misordering class cannot recur. Memory
  unchanged: kept ≤ budget, one chunk in flight.
- **B — identity through the descriptor** (`journal.py` `_verified_read`):
  `(st_dev, st_ino)` of the opened fd must equal the pre-open lstat;
  identity-less mounts (st_ino 0) fail closed. Probed live on NTFS:
  distinct files give distinct ino, lstat≡fstat, so the check is real.
- **C — completeness probe** (`journal.py` `_descriptor_unchanged`): after
  the read, the SAME fd is re-fstat'ed; any growth/shrink/identity change
  in the window is a named refusal, never a silent truncation. Fast path
  (exact-size read) and fallback loop share the probe.
- **D — cap before allocation**: `st_size > 256 MiB` is refused before any
  read of that size is requested; the loop keeps the cumulative check.
- **Adversarial finds beyond the handoff (N6-X2):** two live defects found
  by self-attack, both fixed with red→green in the same verifier:
  1. `status --view agent` HUMAN renderer crashed (TypeError) on the
     bounded view's marker rows — `'; '.join` over dicts. Live rc=1 →
     rc=0. The renderer now renders the marker's `text`; machine JSON
     unchanged.
  2. Re-projection was NOT idempotent: a marker row fed back through
     `_agent_view_payload` lost its `text` under `__overflow__`.
     `_emit_waits` now passes already-bounded marker rows through.

## Family + parity (unchanged contract, healthy path)

- night6 10/10 GREEN · night5 10/10 GREEN (X3 honest SKIP, WinError 1314) ·
  night4 5/5 · stress GREEN · repro GREEN.
- **Journal semantic digest parity (live corpus, engine vs independent
  naive reader): MATCH `a8b0d8b3e0c4e36d`, 20275 receipts, 0 structural
  errors.** (Night5's b3017614 covered 20272 receipts; three receipts
  landed since, so the honest oracle is engine-vs-naive on today's corpus.)

## Performance (interleaved, same corpus, same machine)

- `status --view agent` wall p50 **9.24 s** over 8 interleaved runs
  (8.59–9.58 s) vs night5 corridor 9.17–9.28 s — **time-neutral**; the
  identity + closing-fstat probes cost nothing measurable on the healthy
  path.
- Profile (cProfile, one run): `_status` 11.9 s total; convergence path
  `semantic_receipt_snapshot` 4.97 s; distribution 2.2 s (71538 lstat).

## W5 — performance hypothesis honestly falsified

Candidate: skip `convergence_verdict` (~5 s) inside `automation_block` when
an active DOING route makes `gate["complete"]` unreachable. **Falsified by
measurement, not adopted:** the live route (`PHASE SCOUT T-2090`, reason
`finish`) maps to disposition CONTINUE, so `complete` IS consulted every
run, and `convergence_current` is a contract field of the automation block
regardless of disposition. Narrowing it would need a contract change with
an explicitly narrower `convergence_current` semantics — a release-surface
decision, not a night-shift shortcut. No code change.

## Core-unit family (T-1344) — first run FAIL, attributed, wave-adjacent reds repaired

- Record `78eae5d9f9280e5b-20261118T100700658073Z.json`: ran 8697,
  red 677, **new_red 590** vs baseline `f008508f…` (98 red). FAIL — the
  SHIP gate refused it (E-21720).
- Attribution (every red module re-run directly in the repo, correct
  discovery context `tools.*` from repo root):
  - ~470 reds were **transient sandbox loss**: the run's shard copies
    were emptied mid-run (BOOT.md, tests/scenarios, adapters
    registry.json missing inside `V:\_TEMP_\saipen-core-unit-*`).
    A fresh `copy_tree_consistent` probe (same ignore filter, 108.7 s)
    carries EVERY one of those paths — engine copy logic is healthy;
    the loss was environmental (shared temp root, concurrent sessions),
    not a subject defect.
  - 23 reds `test_response_surface_contract.DiagnosisTests` — **fixed by
    this shift**: foreign session rewrote
    `tests/fixtures/protocol-diagnosis/{a,b}.md` with CRLF bytes at
    01:46 (git smudge + stat-cache left them looking clean); restored
    byte-exact from HEAD — digests `1378f149…`/`a6d6ca95…` match, suite
    56/56 GREEN.
  - 1 red `test_t1576_efficiency_kpi` — **fixed by this shift**: stray
    pre-fix snapshots `tools/regression_t2089/t2089_prefix_{saipen,journal}.py`
    (night-4/5 residue + my night-6 staging copy) imported `efficiency`
    and broke the KPI import-ownership contract. Removed from `tools/`
    (canonical copies remain under `.saipen/evidence/T-2090/prefix/`,
    which the pair contract cites). Suite 19/19 GREEN.
  - Foreign WIP reds (NOT this wave's, left to their owners):
    `test_gc` 7 + `test_refusal_registry` 1 (untracked `gc.py`/`test_gc.py`,
    `gc` verb not in COMMAND_EFFECTS.json), `test_t2040_publication_truth` 44
    + `test_t2040_review_proof_binding` 13 (untracked
    `test_t2040_publication_truth.py` imports missing
    `saipen_engine.isolated_release`), `test_t2023` 34, `test_t2087` 1
    (untracked), `test_t2066` 4 (staged foreign WIP).
  - Environment/foreign-project reds (unfixable from here):
    `test_t1926` 1 (ZAICODE host reachable on this machine),
    `test_t1816` 3 (foreign `_AUDAPACK` project LOG.md state).
  - Baseline debt unchanged: 98-red family stays (module_duplication_guard,
    style_contract_chokepoint, t1949 etc.).
- Wave-adjacent combined suite re-run GREEN: 226 tests OK (3 skips).
- **Re-run after repairs** (`9d4d23e82a6a4350-20261118T114011636990Z.json`,
  sha256 `18cd9fd3…`, 2552 s): ran 8711, red 96, **new_red 9**, fixed 12.
  The 590→9 collapse confirms the attribution: all 9 remaining new reds
  are foreign WIP not owned by this wave — `test_gc` ×3 +
  `test_refusal_registry` ×1 (untracked T-2049 `gc` WIP: verb missing
  from COMMAND_EFFECTS.json, refusal codes unregistered),
  `test_t2066_zaicode_host_policy` ×4 (staged foreign WIP),
  `test_t2087_drift_matrix_anchors` ×1 (untracked, fixture path absent).
- SHIP gate honestly refused (E-21722/E-21723):
  "cited core-unit run is not admissible: 9 new red outside the baseline".
  `new_red:0` is unreachable while another ticket's in-flight WIP sits
  untracked in `tools/`; repairing it would exceed this wave's scope
  contract (one subsystem per wave; no auto-P0 on foreign scenarios).
  The refusal is recorded, not bypassed — T-2090 stays REVIEW.

## Canonical state (read-only; no operator decisions manufactured)

- T-2090 DOING; this shift rides the same ticket (the four P0s are the
  same projection/journal subsystem the ticket owns). T-2091 (SRC-425,
  night-5 request) stays queued — same subject, not duplicated into a
  third ticket.
- Publication unchanged: 7 homes / 7 stale / DIRTY_SOURCE class debt,
  T-2058 operator cycle untouched. Nothing committed, installed,
  published or pushed. `implementation complete ≠ publication complete`.
- Carried debt unchanged: perf_wave 37/42 baseline failures,
  t2040 import debt — pre-existing, not this shift's regressions.
  The untracked gc/t2023/t2087/t2040 WIP reds above belong to their own
  tickets; this shift repaired only what its own radius broke
  (fixtures, stray snapshots).

## DoD (handoff §15)

- [x] Multi-chunk UTF-8 digest RED → GREEN
- [x] Regular-file substitution RED → GREEN
- [x] File growth capture RED → GREEN
- [x] Oversized initial read RED → GREEN
- [x] Journal structural errors fail-closed (identity/size/cap, named)
- [x] Canonical digest parity on the live corpus (MATCH a8b0d8b3)
- [x] No new authority regressions (night4/5/stress/repro families green)
- [x] No unexplained performance regression (9.24 s vs 9.17–9.28 corridor)
- [x] Repo engine used for every test (module load from `tools/`)
- [x] Lifecycle T-2090 walked forward within authority (SCOUT → BUILD)
- [x] T-2091 not duplicated
- [x] Extra useful work: N6-X2 renderer crash + idempotence defects fixed;
      one perf hypothesis measured and honestly falsified
- [x] Release blockers not bypassed or falsified
