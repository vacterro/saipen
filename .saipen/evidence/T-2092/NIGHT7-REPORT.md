# NIGHT SHIFT 7 REPORT — 2026-11-18 (T-2092, SRC-426)

**STATUS: PARTIAL** (own Work DONE; T-2090/91 blocked on foreign WIP; publication debt pre-existing)

## CANONICAL STATE

- HEAD `dc39709c0`, branch `main`, worktree dirty (57 106 paths, foreign WIP dominant)
- STATE: phase DONE, task none, last_event E-21738, next_action `saipen validate`
- T-2090: **BLOCKED** (E-21726) — REVIEW verdict NO--BLOCKER (E-21725); own oracle PASS
- T-2091: **BLOCKED** (E-21727) — obligations N5-A..N5-E covered by T-2090 evidence (NIGHT5 10/10); co-gated on T-2090 SHIP; no duplicate work
- T-2092: **DONE** (E-21737, own_patch, publication_state pending); SRC-426 closed
- T-2047 reverify: PASS_WITH_CARRIED_DEBT (RV-000095)

## THE NINE new_red — OWNERSHIP (live-confirmed, focused, no 42-min re-run)

| Group | Count | Owner | Cause |
|---|---|---|---|
| test_gc + refusal registry | 3+1 | T-2049 foreign WIP | untracked `gc.py`/`test_gc.py`; `gc` verb missing from COMMAND_EFFECTS; 7 GC refusal codes unregistered |
| test_t2066 host policy | 4 | T-2066 foreign WIP | staged test file, no shipped implementation |
| test_t2087 drift anchors | 1 | stale fixture | test reads BZDECOMP `intake/active/SRC-803..805`; receipt tombstoned lawfully; test path stale |

Baseline untouched. No fake closure, no baseline growth. ROOT_CAUSE for the
590→9 night-6 collapse stands as reported (environmental transient sandbox
loss); not reproduced under stress (below).

## W1 — SANDBOX RELIABILITY (proven defects, RED→GREEN)

Hermetic suite `tools/test_t2092_concurrent_family_isolation.py` (10 tests):
two concurrent real `run_family` runs, sweep-vs-copy race, foreign project,
live creator/reader guards, unknown ownership, PID-grammar fault injection —
all on disposable temp roots.

Three proven defects FIXED in `tools/saipen_engine/core_unit.py`:

1. **V4 violation (sweep)**: a stamp naming no usable process (missing/non-int
   pid) was treated as "no live owner" → deleted. Now unknown ownership refuses
   (fail-closed).
2. **V4 violation (sweep)**: non-int pid values crashed the liveness grammar
   into a stale verdict. Now refused as unknown ownership.
3. **stamp-clobber (reclaim)**: `reclaim` re-read the owner stamp every retry,
   so a foreign writer's bytes were restored by MY cleanup — the tree then
   answered to a foreign `verification_flight`. Now the restore replays only
   the bytes the cleanup STARTED from.

Live-sandbox protection (V1/V2/V5/V6) re-proven GREEN: a live creator or
reader blocks every sweep; two concurrent runs never share or reclaim each
other's sandboxes; a foreign project's sandbox is never touched. Windows PID
reuse guarded by `pid_created` (existing, retained).

## W5 — AUTONOMY (proven, no code change needed)

`tools/test_t2092_flight_replay_recovery.py` (2 tests): a published FAIL of
the exact identity replays to a LATER PROCESS as FAIL (persistent
`single_flight` cache) — the repeated identical 42-min re-run is refused
cheaply; a changed tree never replays the old verdict. The autonomy loop of
§6.1 is therefore already closed by existing capability; what remained was
proof, now recorded.

## W2 — VERIFICATION COST (measured honestly)

- Full copy: 2.56 GiB; `.saipen` 2.07 GiB (evidence 1.47 GiB), `.git` 0.47 GiB.
- Focused FULL copy measured 620–676 s on this disk — the 300 s focused budget
  cannot carry it (two diagnostic FAIL records E-21731/E-21732, kept as evidence).
- After declaring the two new modules in `tools/sandbox_scope.json` (T-1889
  rule: declare after a narrowed GREEN run — this run is that evidence), the
  same focused verification ran in a DECLARED sandbox: **copy 40 s, PASS 12/12**
  (E-21733). ~620 s → ~40 s for declared modules; that is the honest lever.
- Narrowing the FULL family requires per-module declarations for all 605
  modules (T-1889 evidence campaign). No shortcut taken: the resolver refuses
  one undeclared module and copies everything — by design (INV-20).

## REGRESSIONS (all GREEN)

t1505 21/21 · t1479 4/4 · t1472 14/14 · core_unit_gate 28/28 · night4 5/5 ·
night5 10/10 (1 honest SKIP) · night6 10/10 · repro 0 RED/3 GREEN · stress GREEN.
t1832 RealConcurrentCli 3 reds proven PRE-EXISTING (git-stash control, not
this delta; slow-disk CLI fixture class).

## CODE (this shift's delta)

- `tools/saipen_engine/core_unit.py` — V4 sweep refusal + reclaim first-read restore (fail-closed, minimal)
- `tools/test_t2092_concurrent_family_isolation.py` — NEW hermetic concurrency suite
- `tools/test_t2092_flight_replay_recovery.py` — NEW cross-process replay proof
- `tools/sandbox_scope.json` — 2 declarations for the new modules (narrowed-copy evidence)

## RELEASE / VALIDATE

implemented ✓ committed ✗ installed ✗ published ✗ (publication_state pending,
same route as T-2089/T-2087: `saipen cohort ship` flips it when the operator
authorizes). `saipen validate`: CONFORMANCE_UNHEALTHY — disposition E-21738:
`closure_provenance_drift` EX-000053 sits on T-2058 release staging
(operator decision E-21497); 48 `runtime_manifest_untracked` are foreign
untracked/staged WIP (gc.py, test_gc.py, t2066, t2089 verifiers); board-soft-cap
warn ownership is T-401 debt. None introduced by this delta.

## BLOCKERS (genuine, remaining)

1. T-2058 publication staging authority (operator decision) — gates every
   pending publication including T-2090's SHIP and EX-000053 conformance.
2. Foreign WIP reds (T-2049 gc, T-2066, T-2087 fixture) — owners must land
   or retire them; T-2090 SHIP needs their 9 reds gone from the shared tree.
3. 57 106-path dirty worktree blocks any honest Git publication chain.

## NEXT EXACT ACTION

`saipen claim T-2090` — with the foreign gc/t2066/t2087 WIP resolved by their
owners (or with operator authority over it), re-run ONLY the four focused
foreign suites (minutes, not 42 min); when all 9 reds clear, `saipen
transition SHIP T-2090` cites the existing PASS record `9d4d...` — no full
re-run required unless the tree fingerprint changed.
