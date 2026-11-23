# T-1900 — the source-identity Git listing asks Git for its own boundary

**Subject.** `tools/freshness.py::_git_delta_listing` — the changed-path listing
that `compute_source_identity` fingerprints.

**Defect (measured, not hypothesised).** The source identity excludes `.saipen`:
`_parse_git_delta` skips those paths and `_filtered_git_listing` projects them
out before every comparison. But both Git invocations were issued with no
pathspec at all, so Git generated the entire `.saipen` population and this
process decoded it, only to throw it away:

| measure | value |
| --- | --- |
| untracked paths Git emitted | 42 578 |
| untracked paths the identity keeps | 57 |
| discarded by `_is_saipen_path` afterwards | 42 521 |
| `ls-files` bytes produced per pass | 4 179 811 → 2 497 |
| listings per `compute_source_identity` | 3 |
| measured `_git_delta_listing` pair, pre-fix | 0.9953 s |

The cost was paid three times per capture, and `compute_source_identity` is what
`require_fresh`, the improve strict-cycle bar, `saipen improve verify`, and the
discovery gate all read.

## Change

One edit: both Git calls receive `_SAIPEN_PATHSPEC = (":(exclude).saipen",)`.

Exclusion-only, deliberately. Git selects relative to the caller's directory, so
omitting a positive pathspec preserves that selection exactly; adding `.` beside
the exclusion would be redundant, and using `:/` would WIDEN it to the repository
top level. The measurement below pins the widening case, because `:/` plus the
exclusion really does make a subdirectory project start fingerprinting
`../../outside-new.txt`.

Nothing else moved. `_filtered_git_listing`, `_parse_git_delta`, the
three-listing equality proof, both HEAD reads, the record re-parse confirmation
and the nested-repo binding are all unchanged, and they keep their own
`_is_saipen_path` predicate — so a Git that ignored the pathspec could only cost
time, never correctness. The exact same pathspec spelling already exists in the
engine at `convergence.py:429`.

## Before / after — same tree, same bytes, alternating runs

Both halves run on the SAME working tree, alternating so machine drift is shared.
The only difference between them is the two Git invocations.

| | pre-fix | post-fix |
| --- | --- | --- |
| `compute_source_identity` median (4 alternating runs) | 3.894 s | 1.108 s |
| `compute_source_identity` min | 3.818 s | 1.079 s |
| `_git_delta_listing` pair, min | 0.9953 s | 0.1076 s (9.2×) |
| `source_head` | `025bf596c6834647…` | identical |
| `source_tree_fingerprint` | `git-delta-v1:c874da1c555c78d7…` | **identical** |

**Verdict: 3.51× faster capture, 71.5 % less wall, fingerprint byte-identical.**
The end-to-end effect on `saipen continue` is not claimed here: this repository's
`.saipen` tree cannot be mirrored into a scratch copy cheaply enough to build an
honest two-tree `continue` comparison (1.8 GB, and a copy without `.git` falls
back to the no-Git discovery model, which is a different workload). What is
claimed is the unit that was measured, on identical bytes.

## Regression pair

Verifier `d85e5dc48c936b73` — `tools/test_t1900_git_listing_boundary.py`,
identical bytes on both halves, five cases.

| half | subject | result |
| --- | --- | --- |
| FAIL | `50b9916b1b39a284` | 2 of 5 red — AC-01 reports the listing still carrying `.saipen/STATE.md` and `.saipen/deep/nested/BOARD.md`; AC-05 reports the outer fingerprint MOVING when only a declared nested repository's `.saipen` changed |
| PASS | `4f04245357aa4170` | 5 of 5 green |

The prefix tree is the whole project copied to `V:/_TEMP_/t1900-prefix` with
ONLY the pathspec hunk reverted to the literal pre-fix function body.

Journal records: `E-18057` (FAIL) / `E-18058` (PASS). These supersede
`E-18053`/`E-18054`, which were recorded against the pre-AC-05 verifier bytes;
the production gate `log.regression_evidence("T-1900", …)` returns
`ADMISSIBLE` on the current pair.

AC-02 (surviving set equal to an unpathspeced control), AC-03 (scope neither
narrowed nor widened) and AC-04 (an `.saipen`-only change never moves the
identity) are non-regression invariants that hold on both trees by
construction. They exist to fail if a future edit breaks equivalence, not to be
red today. AC-05 is red on the prefix tree, because the pathspec reaches a
consumer that does NOT filter.

## AC-05 — the one semantic change this ticket does make

`_nested_binding` hashes a declared nested repository's listing verbatim
(`SHA256(raw_delta + b"\0" + untracked)`) instead of filtering it through
`_is_saipen_path`. Before T-1900 the nested listing therefore carried
`inner/.saipen/STATE.md`, and a nested project's runtime churn moved the OUTER
project's fingerprint. After T-1900 it does not.

Measured on a two-tree fixture (outer repo declaring `inner` via
`.saipen/source-nested-repos.json`, `inner/` gitignored):

| mutation | prefix | post-fix |
| --- | --- | --- |
| `inner/code2.py` (nested SOURCE) | outer fingerprint moves | outer fingerprint moves |
| `inner/.saipen/STATE.md` (nested RUNTIME) | outer fingerprint moves | **outer fingerprint unchanged** |
| `inner/.saipen-src/keep.py` (lookalike) | binds | binds |
| `inner/.saipenx/y.py` | binds | binds |
| `inner/.saipenicious.py` | binds | binds |

This direction is the correct one — a nested project's `.saipen` is that
project's runtime, exactly as the outer project's `.saipen` is the outer one's —
but it is a real behaviour change, so AC-05 pins it rather than letting it ride
along inside a "cost-only" claim. The live project declares no nested repos
(`_nested_binding` returns `b""`), so its own fingerprint is unaffected.

## What this does NOT claim

- It does not bound the `.saipen` population itself. The 42 521 paths are still
  on disk; Git is simply no longer asked to enumerate them. Shrinking that tree
  is separate work with its own retention rules (INV-14).
- It does not speed up `status` or `continue` by a stated percentage. Those
  paths were profiled, and `read_history_snapshot` (1.336 s over 2 calls inside
  `continue`) is the next independent target, not a consequence of this one.
- It does not change what the identity covers. The fingerprint is byte-identical
  on the live tree, and the subdirectory case proves the scope is preserved in
  both directions.

## Cross-family results

| family | result |
| --- | --- |
| `test_t1900_git_listing_boundary.py` | 5 passed |
| `test_nested_source_binding.py` | 13 passed (both trees) |
| `test_t1891_freshness_parser.py` | 12 passed |
| `test_t1511_soak_source_identity.py` | 7 passed, `source_integrity: STABLE` |
| `core_unit.py focused T-1900` (both patterns) | 18 ran, PASS, 134.4 s — `.saipen/evidence/focused-unit/c8514d37bf62a18e-20261025T022039487701Z.json` |
| `perf_wave_regressions.py` | 39/42 — the 3 failures are a pre-existing `TypeError: witnessed_operator() missing 1 required positional argument: 'root'` at `run_scenarios.py:13935`, in a file this ticket did not touch |
| `test_concurrency_independence.py` | 1 error, inherited: `ModuleNotFoundError: No module named 'tools'` when run directly — reproduces identically on the untouched prefix tree |

## RE-VERIFY — the campaign handoff's T20 requirement

The handoff asked for a real `compute_source_identity` wall-clock number, not
only one Git subcommand. Measured on the live tree at 2026-10-25T04:16Z, both
halves on the SAME bytes, alternating so machine drift is shared:

| | pre-fix function | post-fix function |
| --- | --- | --- |
| `compute_source_identity` min | 3.090 s | 0.961 s |
| `compute_source_identity` median (4 alternating) | 3.157 s | 1.003 s |
| `_git_delta_listing` pair | 0.749 s | 0.110 s (6.8×) |
| untracked paths Git emitted | 42 584 | 58 |
| `source_tree_fingerprint` | `git-delta-v1:29847d860f80780b…` | **identical** |
| `source_head` | `025bf596c6834647…` | identical |

The pre-fix half is the real pre-T-1900 function body injected at runtime, not a
re-simulated cost, so this is a same-tree same-bytes pair. It still bounds only
the identity capture: `saipen continue`'s other costs are untouched.
