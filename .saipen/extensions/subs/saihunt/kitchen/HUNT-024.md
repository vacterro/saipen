# HUNT-024 -- bounded six-signal sweep at dc39709c / tree cf7cd4a7

- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:cf7cd4a7512b88c0b0f2e57a05d17aef9e41b432f907486635c87aa3ab53aa42
- role_revision: sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5
- method: bounded sensor pass, one verdict per signal, no main-project write.

The tree moved from f3dab073 (HUNT-023) to cf7cd4a7 after the T-2077 head-only
unblock classifier landed in the worktree, so this pass re-measured both gates
and the censuses at the live identity. Head is unchanged (dc39709c).

## Signal 1 -- failing tests: REPRODUCED, every class already owned

Installed canonical gate (`saipen validate --json`, capture
`_hunt024_installed_validate.json`, receipt
`.saipen/recovery/conformance/2026-11-17T08_54_26.276276Z_receipt-b06bbfb893e2_core_FAIL.json`):

- exit 1, `CONFORMANCE_UNHEALTHY`, 2 problems / 16 warnings, structural gate pass.
- install identity MATCH `install-v1:c8b61d5b...` (scheduled-source).
- P1: `STATE.md audit route not followed -- the audit inbox routes 'saipen audit
  ingest' (audit/SAIHANDOFF_BZ_REA_AGENT_DRIFT_RECOVERY.md) but next_action is
  'saipen crew' ...` -- installed 8.1.0 pre-fix `audit_route.py`.
- P2: `FUTURE GATE: future gate FG-0046 names slice ticket T-1936, which is not
  on BOARD` -- installed 8.1.0 pre-fix `future_gate.py`.

Repo-generation gate (`python -B tools/validate.py`, capture
`_hunt024_repo_validate.txt`):

- exit 1, `Validation FAILED: 29 problem(s), 37 warning(s)`.
- all 29 problems are the one class `runtime manifest names a file git does not
  track` (29 paths: 5 engine modules, `tools/_t2040_experiment.py`,
  `tools/test_gc.py`, `tools/test_nested_git_boundaries.py`, 11
  `tools/test_t2040_*`, and 9 later `tools/test_t20xx` records including the
  T-2076/T-2077 records).
- zero audit-route failures and zero FUTURE GATE failures: the two worktree
  payload repairs answer the installed gate's two problems.
- `EX-000053 provenance` is not reported by this run, unlike the HUNT-023
  capture at f3dab073.

Focused controls (capture `_hunt024_tests.txt`, two invocations):

- `tools.test_t1430_crew_run_receipt tools.test_audit_route
  tools.test_t2052_pruned_slice_closure tools.test_t2071_gate_pinned_row
  tools.test_gc`: `Ran 112 tests`, `OK (skipped=1)`, exit 0.
- `tools.test_refusal_registry tools.test_t2077_unblock_gate
  tools.test_t2076_installed_generation_binding`: `Ran 17 tests`, `OK`, exit 0.
- This is not a repository harness PASS; the focused set is 129 cases.

Ownership: installed P1/P2 = installed-generation gaps for the already-DONE
payload repairs, cleared only by the T-2058 install route; repo 29 = the known
untracked runtime-manifest class under T-1449/T-2058/T-2052/T-2040. No new
ticket.

## Signal 2 -- commits unverified in LOG: REPRODUCED, already owned

`git log -25 --format=%H` compared by full, 8-char and 12-char literal against
`.saipen/LOG.md`: 1 of 25 cited, 24 uncited (the cited one is the newest HEAD
family). HUNT-022/HUNT-023 measured the same class; it is owned by T-1449 and
T-2057 (lost regression-execution evidence carrier). No claim beyond the
literal census.

## Signal 3 -- stale TODO/FIXME/HACK: NOT_REPRODUCED (bounded)

Census over 175 files (`tools/saipen_engine/*.py`, `tools/saipen.py`,
`tools/validate.py`): 199 marker lines. Exactly one marker line names a DONE
ticket -- `tools/saipen_engine/reconcile.py:1915` `restart: TODO` inside the
T-1609 protocol vocabulary (a state label, not a stale development marker).
Zero stale markers. Limits: literal census only; not every historical marker
was reviewed.

## Signal 4 -- silent failures: no claim

AST census over the same 175 files: 0 bare `except:` handlers, 48
`except ...: pass`-only handlers, 0 parse errors. Counts only; individual
reachability and intent were not reviewed, so no defect is claimed.

## Signal 5 -- symmetry/reachability: REPRODUCED AS FIXED, one documented asymmetry

- `record_crew_run` definition `tools/saipen_engine/operations.py:26301`; one
  live call site `tools/saipen_engine/crew.py:1587` inside `crew_record_run`.
  The T-1430 reachability gap is closed at the producer.
- `record_producer_integration` definition
  `tools/saipen_engine/operations.py:26557`; zero call sites in the scanned
  source. This is the same writer-level asymmetry HUNT-023 documented for the
  SC-8/SC-9 producer stages; it is not newly ticketed here and remains a
  bounded observation, not a proven failure.

## Signal 6 -- dead code/orphans: no claim beyond the manifest class

Bounded listing of untracked `tools/` paths in `git status`: 29 paths, exactly
the same 29 the repo validator names as the untracked runtime-manifest class.
No zero-reference or orphan claim is made beyond that listing.

## Limits

- The monitor counted 4205 `git status --porcelain` lines (7 staged, 3507
  untracked); the dirty injected surface is the known T-2058/T-1449 state and
  was not attributed file by file.
- Signal 2 is a literal census, not a claim that every uncited commit is
  unverified work.
- Signals 3/4/6 are static and bounded, as stated per signal.
- No main-project file was written by this role.
