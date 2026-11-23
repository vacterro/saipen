# HUNT-025 -- bounded six-signal sweep at dc39709c / tree 0f69fe84

- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:0f69fe84ecb98bfc84e2c33be0bb35ef7310de8bbd75c223f7d6b77232be14d2
- role_revision: sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5
- method: bounded sensor pass, one verdict per signal, no main-project write.

The tree moved from cf7cd4a7 (HUNT-024) to 0f69fe84 while HEAD stayed
dc39709c, so this pass re-measures both gates and every census at the live
identity. The source identity excludes `.saipen` (T-1900 pathspec), so role
writes under the role namespace do not move it; the changed-path listing
covers project paths outside `.saipen`, including the foreign pre-staged
paths of T-1816/T-1817.

## Signal 1 -- failing tests: REPRODUCED, every class already owned

Installed canonical gate (`saipen validate --json`, capture
`_hunt025_installed_validate.json`):

- exit 1, `CONFORMANCE_UNHEALTHY`, `CURRENT_FAIL`, structural gate `pass`,
  install identity `MATCH` (scheduled-source), repair `ENGINEERING_REQUIRED`
  with `engine_work_count: 0`, `operator_action_count: 0`.
- installed validator: `Validation FAILED: 2 problem(s), 16 warning(s)` — the
  same two installed-generation gaps HUNT-024 measured (P1 audit-route under
  the installed pre-fix `audit_route.py`; P2 `FUTURE GATE FG-0046` names slice
  T-1936, absent from BOARD). Both are payload repairs already DONE in the
  repo generation and carried only by the T-2058 install route.
- new observation in the same gate: `WARN [producer-package-stale]`
  `.saipen/extensions/subs/saiwiki/kitchen/OUTBOX.md [W-051]` carries
  `git-delta-v1:f6e0d368…` while the live tree computes `0f69fe84…`; it is
  stale and must not be collected, and it FAILs only `--gate collect:saiwiki`.
  It blocks nothing in the core gate.

Repo-generation gate (`python -B tools/validate.py`, capture
`_hunt025_repo_validate.txt`):

- exit 1, `Validation FAILED: 31 problem(s), 39 warning(s)`.
- all 31 problems are the one class `runtime manifest names a file git does
  not track` (31 paths, starting `tools/_t2040_experiment.py`, five engine
  modules, `tools/validate.py` itself, and the 11 `tools/test_t2040_*`
  records plus later `test_t20xx` records).
- the count moved 29 -> 31 since HUNT-024 on the same one class; no second
  problem class appeared, and signal 6's untracked listing is the same 31.

Focused controls (capture `_hunt025_signals.txt`):

- `tools.test_t1430_crew_run_receipt tools.test_audit_route
  tools.test_t2052_pruned_slice_closure tools.test_t2071_gate_pinned_row
  tools.test_gc`: `Ran 112 tests`, `OK (skipped=1)`, exit 0.
- `tools.test_refusal_registry tools.test_t2077_unblock_gate
  tools.test_t2076_installed_generation_binding`: `Ran 17 tests`, `OK`,
  exit 0.
- This is not a repository harness PASS; the focused set is 129 cases.

Ownership: installed P1/P2 = installed-generation gaps for already-DONE
payload repairs, cleared only by the T-2058 install route; repo 31 = the known
untracked runtime-manifest class under T-1449/T-2058/T-2052/T-2040; saiwiki
W-051 = a stale producer package, its own collection gate. No new ticket.

## Signal 2 -- commits unverified in LOG: REPRODUCED, already owned

`git log -25 --format=%H` compared by full, 12-char and 8-char literal against
`.saipen/LOG.md`: 2 of 25 cited, 23 uncited. HUNT-022/023/024 measured the
same class; it is owned by T-1449 and T-2057 (lost regression-execution
evidence carrier). No claim beyond the literal census.

## Signal 3 -- stale TODO/FIXME/HACK: NOT_REPRODUCED (bounded)

Census over 175 files (`tools/saipen_engine/*.py`, `tools/saipen.py`,
`tools/validate.py`): 199 marker lines. Exactly one line names a DONE ticket —
`tools/saipen_engine/reconcile.py:1915` `restart: TODO`, the T-1609 protocol
vocabulary label HUNT-024 identified, not a stale development marker. Zero
stale markers. Limits: literal census only.

## Signal 4 -- silent failures: no claim

AST census over the same 175 files: 0 bare `except:` handlers, 48
`except ...: pass`-only handlers, 0 parse errors. Counts only; reachability
and intent were not reviewed, so no defect is claimed.

## Signal 5 -- symmetry/reachability: REPRODUCED AS FIXED, one documented asymmetry

- `record_crew_run` definition `tools/saipen_engine/operations.py:26461`;
  one live call site `tools/saipen_engine/crew.py:1587` inside
  `crew_record_run`. The T-1430 reachability gap is closed at the producer.
- `record_producer_integration` definition
  `tools/saipen_engine/operations.py:26717`; zero call sites in the scanned
  source. This is the same writer-level asymmetry HUNT-023/HUNT-024
  documented; it is not newly ticketed here and remains a bounded observation.

## Signal 6 -- dead code/orphans: no claim beyond the manifest class

`git ls-files --others --exclude-standard tools` lists 31 paths, exactly the
31 the repo validator names. No zero-reference or orphan claim is made beyond
that listing.

## Limits

- The monitor counted the foreign dirty surface but did not attribute it file
  by file; the known T-2058/T-1449 injected state is unchanged.
- Signals 2/3/4/6 are literal or static censuses, as stated per signal.
- The installed gate's two problems are pre-fix installed-generation gaps, not
  live product defects in the repo generation.
- No main-project file was written; every capture is inside
  `saihunt/kitchen/`.
