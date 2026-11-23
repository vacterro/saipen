# T-2090 — SAIPEN Hyperlean Night Shift 4 — final report

Date: 2026-11-18. Agent: GLM 5.3 (ZCode session). Tree: `dc39709c0` (dirty,
publication-debt class, unchanged by this shift's policy).

## W0 — agent projection P0 defects (handoff §2): FIXED + RED→GREEN

RED first, live tree, before any fix (`tools/regression_t2089/t2089_p0_night4.py`):

- **N4-A** long root ID → `JSONDecodeError: Unterminated string` (truncated-JSON
  round-trip in `_agent_view_payload`). RED reproduced.
- **N4-B** nested 1 MB `distribution` → 1 000 141 B view, `truncated: false`;
  nested 200 KB `conformance_status` → 200 144 B; 200 000-char
  `shared_blocker_id` → 200 482 B. All bypassed the 32 KiB budget. RED.
- **N4-C** deep-copy via `json.loads(json.dumps(...))`: 2 MB input →
  2 000 171 B view, 3 001 642 B peak allocation. RED.
- **N4-E** newline-joined `_cap_digest`: `["a\nb","c"]` vs `["a","b\nc"]`
  collided to one sha256 (`b8e10a62…`). RED.
- **N4-D** dead `for group in groups: pass` loop: removed by the rewrite (the
  source scan in the suite now proves absence).

Fix: `_agent_view_payload` rewritten as a bounded structural build
(tools/saipen.py):

- no truncated-JSON round-trip (long IDs can never raise);
- global 32 KiB UTF-8 budget with per-key charges; nested megabyte values in
  `distribution`/`convergence`/`conformance_status` collapse to digest markers;
- authority-critical string fields (`next_action`, `code`, verdicts) stay
  PLAIN STRINGS under any input — cuts land in
  `authority_text_truncation`, never a marker-dict a consumer could
  mistake for an executable value;
- strings streamed in 32 KiB chunks — projection cost proportional to the
  OUTPUT budget, not input size; no whole-value serialization;
- length-framed (8-byte count + type tag) digest preimage — element splits
  cannot collide; digest work itself capped (64 items / 64 K chars, honest
  `overflow_digest_capped`);
- depth cap 6 with digest markers; non-JSON values named by type + digest;
  exact counts everywhere; honest `truncated`; dead loop gone.

Verification: night-4 suite 5/5 GREEN; existing T-2089 repro 0 RED / 3 GREEN;
stress suite (120/2000/10000 groups, 1–20 parity sweep, 40-trial
mutation/idempotence, truncation truth) GREEN; oracle OK; agent-status-view
parity 4/4; lazy entrypoints 4/4; adversarial edge sweep GREEN (cycles,
surrogates, non-JSON sets, 4000-key dicts, purity, idempotence).
10 000-group + 2 MB-nested projection: **9 ms wall, 191 KiB peak, 21.8 KiB
view** (pre-fix: seconds, MB-scale peak).

## W1 — real status speedup: 13.12 s → 9.42 s p50 (−28%), three measured fixes

Baseline (5 runs, same machine/tree): agent status p50 13.12 s; full 12.35 s.
cProfile hot map: nt.lstat 94 814 × 3.07 s; convergence 6.6 s; distribution
2.7 s; reconcile 2.2 s.

1. **`copy_tree_members` prune-before-lstat** (tools/saipen_engine/manifest.py):
   cache dirs were lstat'd before being pruned — a symlinked/junctioned cache
   dir inside `tools/` failed surfaces that previously passed. Prune order
   fixed; root.resolve() hoisted out of the loop. Proof: cache junction
   PRUNED, normal junction still REFUSED (same error text);
   `runtime_surface_items` parity; generation identity parity MATCH
   (`gen-sha256:cf974df5…`); t1879 manifest family 14/14 OK.
2. **`_receipt_namespace_entries` scandir pass** (tools/saipen_engine/journal.py):
   per-receipt 3 × `os.lstat` + 2 Path constructions replaced by one scandir
   with `entry.stat(follow_symlinks=False)`; reads through os-level
   descriptors. Same verdicts, same detail strings, same name ordering, same
   framed bytes: `semantic_receipt_digest` byte-identical pre/post
   (`ops-receipt-sha256:f6eaed58…`, 3.47 s → 2.30 s); 20 000-dir corpus
   3.25 s → 0.61 s (5.3×); structural shape parity proven (junction,
   vanished, non-dir, no-manifest, progress-junction).
3. **History-detail root identity threading** (tools/saipen_engine/log.py):
   795 compacted-event restorations per pass each re-ran
   `root.resolve().as_posix()` (full ntpath realpath). `_restored_detail_text`
   gains `root_identity=`; the three readers resolve once per pass. A/B on
   the same tree: 0 verdict mismatches; snapshot 0.62 s → 0.33 s. (One
   NameError in the digest reader caught by test_continue_chain before it
   could ship — fixed, families re-run.)

Post-fix (10 runs): agent p50 **9.42 s** (p95 9.74, min 8.90); full 9.62 s;
`--help` 0.18 s. nt.lstat per status: **94 814 → 74 532**.

Honest no-cut findings (recorded, not papered over):

- distribution report 2.0 s = 9 distinct root hashes under one
  `identity_session` (session IS effective; 61 calls collapse to 9 real
  expansions) — every hash is gate-required (expected generation + per-home
  `generation_current` + delegated hook). No safe reduction without
  weakening the freshness gate.
- convergence journal scan (~4.6 s total pass) reads and frames 84.2 MB of
  settled receipts by contract (memo spares decode, never the read).
- reconcile's 2.1 s includes log digest + validate_texts — load-bearing.
- Remaining lstat volume is the receipt namespace contract itself
  (20 270 settled receipts × per-file stat): mechanical to fuse further only
  by weakening per-file shape verdicts. Not done.

## W2 — characterization of `_plan_finish_ticket` (first monolith seam)

`t2040` finish-plan family: blocked by PRE-EXISTING import debt
(`replenishment` missing from `saipen_engine`; fails identically on stashed
baseline) — not this shift's regression.

Independent golden suite landed: `tools/test_t2090_finish_golden.py`, 7/7 OK,
real engine helpers, hermetic trees. Pinned contract: ILLEGAL_PHASE refusals
from SCOUT/BUILD/VERIFY/REVIEW with ZERO canonical writes; DONE-shape
refuses ILLEGAL_TICKET_LIFECYCLE; wrong-ticket refusal writes nothing; SHIP
finish moves LOG/BOARD/STATE atomically (phase DONE, task none, DOING→DONE,
one completion event); repeat finish → ALREADY_APPLIED with no second event;
digest-bearing closure carries the digest INSIDE the same plan transaction
(`.saipen/kitchen/digest.md` target); plan targets are the canonical trio.

## W4 — runtime identity + release gates (read-only re-measure)

- Git HEAD: `dc39709c0c17a3272126c01a626ffcaa4176140b`, dirty (4 370 changed
  paths — pre-existing publication debt).
- Repo generation: `gen-sha256:6376ebd7…`; installed
  (`C:/Users/vac34/AppData/Local/saipen/scheduled-source`):
  `gen-sha256:cf974df5…` — repo ≠ installed (repo holds this shift's engine
  edits; installed remains the last committed generation).
- Distribution: 7 homes installed, 7 stale, `fresh: false`;
  blocker `DIRTY_SOURCE` — 86 injected-surface paths differ from HEAD, so the
  injector refuses to publish. newest_installed_head `7857dbf2` (predates
  HEAD). Published_head: null; pending_consumers: []; requires_human: false.
- `validate.py --no-receipt`: 44 FAIL / 41 WARN. Classification:
  42 = runtime-manifest files git does not track, of which 40 pre-exist
  (publication debt) and 2 are THIS shift's new test files
  (`t2089_p0_night4.py`, `test_t2090_finish_golden.py`) — tracked only by a
  commit, which is the T-2058 operator publication cycle, not mine to force.
  EX-000053 closure provenance FAIL (installed generation moved again) and
  T-2047 reverify FAIL — both the known operator-cycle debt, unchanged here.
- No operator-only decision was manufactured. Publication remains blocked by
  DIRTY_SOURCE exactly as measured.

## Suite ledger (this shift)

All green: night-4 5/5; t2089 repro 0 RED/3 GREEN; t2089 stress; t2089
oracle; agent-status-view 4/4; lazy entrypoints 4/4; t1879 14/14; t1944
22/22; t1903 5/5; t1666 6/6; continue_chain 6/6; t1734 15/15; t1836 OK;
t2090 golden 7/7. perf_wave_regressions: 37/42, 5 FAILs PROVEN pre-existing
(identical on stashed baseline). t2040 family: pre-existing import debt.

## Files changed

- `tools/saipen.py` — `_agent_view_payload` rewrite (the only functional
  change on this route; full projection untouched).
- `tools/saipen_engine/manifest.py` — prune order + hoisted resolve.
- `tools/saipen_engine/journal.py` — scandir capture in
  `_receipt_namespace_entries`.
- `tools/saipen_engine/log.py` — root-identity threading (4 sites).
- NEW `tools/regression_t2089/t2089_p0_night4.py` (verifier, RED-first).
- NEW `tools/test_t2090_finish_golden.py` (characterization).
- No commits, no installs, no pushes, no evidence deletion (operator cycle).
