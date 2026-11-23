# T-2055 — freshness: a valid nested Git directory record is fingerprinted

Cause in the audit carrier: `audit/SAIHANDOFF_SAIPEN_HOME_AUDIT_BZDECOMP_20261113.md` §5.
Incident project: `V:\___VAC\__K\__CODE\_MISC\_BZDECOMP`.
Runtime that failed: `C:\Users\vac34\AppData\Local\saipen\scheduled-source`.
Fix owner: `tools/freshness.py` (`_path_from_git`, `_nested_boundary_from_git`, `_parse_git_delta*`).

## Defect

`git ls-files --others` reported an embedded repository as a DIRECTORY with a
trailing slash:

```
b'contributions/.tooling/upstream-parser/'
```

`_path_from_git` split it on `/`, met an empty final component and aborted the
whole capture with `Git returned a non-canonical path`. The identity was empty,
so `saipen validate` reported `CONFORMANCE_UNHEALTHY` / `STALE_FAIL` /
`source-identity-unavailable`, a condition the validator refuses to auto-cure.
Measured twice before the fix, 2026-11-13T18:46:15Z (receipt-948ed50ec40d, audit)
and 2026-11-14T00:57:13Z (receipt-300d58ee20ec, this ticket, unchanged text):

```
source freshness computation BLOCKED -- Git returned a non-canonical path:
b'contributions/.tooling/upstream-parser/'; no package may become ready or
be collected with unknown input
```

## Fix

A directory boundary that is a Git work-tree root now produces an `N` record
whose content is a deterministic CONTENT identity (`_nested_repository_content`):

* its own `HEAD^{tree}` -- content-addressed, NOT `HEAD`, whose id also folds in
  the commit timestamp/author/message (see "flake" below),
* the sha256 of its own `git diff --raw` delta (blob ids of every tracked
  change and deletion),
* the sha256 over every untracked entry's bytes (same-size/mtime edit still
  moves it), directories inside it via `_tree_content_digest`,
* an unborn `HEAD` falls back to `_tree_content_digest` of the tree.

The record participates in the outer `git-delta-v1` digest under the stripped
relative path, so it carries no absolute path and is identical wherever the
same tree lives. A repository declared in `.saipen/source-nested-repos.json`
keeps its existing `_nested_binding` behaviour and is still skipped here.

Nothing of the user's repository is deleted, moved, ignored or staged: the
capture only reads. Refusals kept: absolute paths, traversal, NUL, symlink or
reparse-point boundaries, a `dir/` entry that is not a repository, and a
declared repository that is missing.

## Regression (same case, pre-fix FAIL -> post-fix PASS)

`tools/test_t2055_nested_directory_fingerprint.py` (16 tests: incident worktree,
independent nested repo, determinism across roots, tracked/untracked/commit
movement, unborn HEAD, repository left untouched, declared contracts, and five
dangerous-input refusals).

Pre-fix, on the unchanged test file:

```
python -m pytest tools/test_t2055_nested_directory_fingerprint.py -q
10 failed, 6 passed
freshness.FreshnessError: untracked nested Git repository
'contributions/.tooling/upstream-parser' has no ownership contract ...
```

Post-fix:

```
python -m pytest tools/test_t2055_nested_directory_fingerprint.py \
    tools/test_nested_git_boundaries.py tools/test_nested_source_binding.py \
    tools/test_t1900_git_listing_boundary.py -q
57 passed

python -m pytest tools/test_t2055_nested_directory_fingerprint.py -q   (three consecutive runs)
16 passed / 16 passed / 16 passed

python -m pytest tools/test_t1902_parallel_source_sampling.py tools/test_concurrency_independence.py \
    tools/test_t1511_soak_source_identity.py -q
23 passed, 1 skipped, 9 subtests passed
```

### The flake this found

Run together with the neighbouring suites, the first version failed
`test_identical_trees_in_different_roots_share_one_fingerprint`: it had been
binding the nested repository's `HEAD`, so two identical trees committed in two
different seconds produced two identities. The test now creates its two
fixtures at two FIXED instants, asserts their commit ids differ, and asserts the
two fingerprints are equal -- the property is pinned deterministically instead
of passing by luck. `_nested_repository_content` now names the tree object.

Contract change recorded in `tools/test_nested_git_boundaries.py`: the three
"undeclared nested repository is refused" cases now assert it is FINGERPRINTED
and that an edit inside it moves the outer identity; the conformance
retry-boundary fixture uses a declared-but-missing repository as the honest
remaining unavailability.

## Live project check (BZDECOMP)

With the FIXED SOURCE engine, the incident project is conformant:

```
cd V:\___VAC\__K\__CODE\_MISC\_BZDECOMP
python V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\tools\validate.py
=> Validation complete. Agent is conformant. (12 warning(s))     [0 problems]
```

Identity of the same tree, computed by the fixed source (`compute_source_identity`):
`git-delta-v1:fde428267e92daf0aa2b61ddb4998dacd96791a84ed2687e478c6fd7f4cd3247`,
head `7c8a31dfd91d49b4bb3b5a96eb6ca546fc3d193e`, 7.4 s (the project declares two
nested repositories, so this now pays for two nested bindings).

The INSTALLED runtime is unchanged and still fails, because publication is
blocked (below):

```
cd V:\___VAC\__K\__CODE\_MISC\_BZDECOMP && saipen validate --json
code: CONFORMANCE_UNHEALTHY   status: STALE_FAIL   stale_reason: source-identity-unavailable
receipt-0510b30e91a0 2026-11-14T01:36:16Z
problem: source freshness computation BLOCKED -- Git returned a non-canonical path:
         b'contributions/.tooling/upstream-parser/'
```

## Runtime publication: blocked, not done

`saipen ship` is refused before any commit:

```
saipen transition SHIP T-2055
=> INCOMPLETE_TICKET: the current VERIFY cycle of T-2055 names no run of the
   declared core-unit family, canonical: python tools/core_unit.py evidence T-2055
```

That run cannot complete on this tree, measured twice:

```
python tools/core_unit.py evidence T-2055            => MemoryError in
   shutil.copytree <- core_unit._copy_saipen_once (2.3 GB .saipen, 52k files)
python tools/core_unit.py evidence T-2055 --jobs 1   => no output within 590 s
```

The publisher that owns `scheduled-source` then refuses the uncommitted surface:

```
powershell -File bootstrap/schedule-run.ps1
=> dirty: ?? tools/test_t2055_nested_directory_fingerprint.py ... SKIP: DIRTY_SOURCE (rc=2)
```

So the official runtime at
`C:\Users\vac34\AppData\Local\saipen\scheduled-source` still carries the defect.
Resume: make the core-unit family runnable on this tree (or a reviewed bounded
`.saipen` copy), ship, then let the scheduled publisher converge the runtime.

## Residual limits

* `tools/freshness_golden_v1.py` is the frozen pre-wave oracle and is NOT
  changed; it still parses no directory boundary, so parity fixtures must not
  contain one.
* `python tools/perf_wave_regressions.py` reports 5 failures (AUDIT PERF-002
  call counts in `release._capture_index_state`, and three T-1022 nitro probes
  raising `TypeError: witnessed_operator() missing 1 required positional
  argument`). Those paths never call `freshness`; they are pre-existing and
  unrelated to this change.
* A declared nested repository's binding still hashes its listing only (not
  untracked bytes). Unchanged on purpose: changing it would move every
  existing declared project's identity.
