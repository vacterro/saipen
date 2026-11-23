# T-1882 correction: the committed HEAD tree is NOT clean

Measured 2026-10-25 during the campaign's baseline revalidation. PARTITION.md
concluded "0 regressions in shipped code that this campaign leaves
unexplained". A family run against the committed revision disproves that
sentence for a small, named set. This file records the measurement and the
method error that first inflated it.

## First measurement was partly a method artifact

`git archive HEAD | tar -x` produces a tree with **no `.git`**. That export was
run with:

    python -B -m unittest discover -s tools -p "test_*.py" -v

Result: `Ran 5073 tests in 2468.861s` / `FAILED (failures=11, skipped=67)`.

Four of those eleven were the export's own fault, not shipped-code defects:

| test | why it failed in the export |
| --- | --- |
| `test_handoff_archive_cross_repo` (3 tests) | the test shells out to `git ls-files`; the export has no `.git`, so git exits 128 and the inventory is empty |
| `test_saipen_metrics.ReportTests.test_collect_and_render` | `machinery_lines()` shells out to `git grep -c '' <rev> -- tools/*.py`; `git()` swallows the failure and returns `""`, so `machinery_lines_now` is 0 and the `> 0` assertion fails |

`git archive` was the wrong instrument for a suite that queries its own
repository. It is recorded here rather than deleted so the number is not
misquoted later.

## Corrected measurement: a real worktree at HEAD

    git worktree add --detach V:/_TEMP_/t1882-wt HEAD

Then, inside `V:/_TEMP_/t1882-wt/tools`:

    python -B -m unittest test_legacy_lifecycle_compat test_saipen_metrics \
        test_handoff_archive_cross_repo -v
    # Ran 59 tests in 20.128s -- FAILED (failures=6, skipped=1)

    python -B -m unittest test_opencode_host_smoke -v
    # Ran 10 tests in 51.690s -- FAILED (failures=1)

So the committed tree carries **7 real failures**, and the two remote-query
families the export blamed both pass in a real worktree.

### The 6 legacy-lifecycle failures

    test_legacy_lifecycle_compat.AttestLegacyDoneTests.test_attestation_clears_the_ambiguity_without_rewriting_history
    test_legacy_lifecycle_compat.AttestLegacyDoneTests.test_cli_attest_round_trip_and_id_grammar
    test_legacy_lifecycle_compat.PlanIdentityTests.test_attestation_plus_approval_commits_both_in_one_pass
    test_legacy_lifecycle_compat.TargetCLegacyDoneTests.test_1_pre_closure_mode_done_with_build_evidence_remains_done
    test_legacy_lifecycle_compat.TargetCLegacyDoneTests.test_2_pre_closure_mode_done_with_ship_evidence_remains_legacy_valid
    test_legacy_lifecycle_compat.TargetDLegacyAttributionTests.test_4_legacy_attribution_survives_a_full_reconciliation

All six fail for one cause: reconciliation answers `RECONCILE_REAUTH_REQUIRED`
for `T-113` and `T-114` (pre-closure-contract `## DONE` rows) instead of
leaving them legacy-valid, and names the operator command
`saipen recover --attest-legacy-done T-113,T-114`.

In the live working tree all 27 tests in that module pass in 0.538 s. The
difference is uncommitted: `tools/saipen_engine/reconcile.py` (+602/-154 lines
against HEAD) and the new module `tools/saipen_engine/goal_authority.py`, both
staged-or-modified but not committed at `025bf596`. Proof that these two files
are the cause, not a guess: copying HEAD's `reconcile.py` aside and importing
the live one in the clean worktree fails immediately at
`from .goal_authority import ...` (`No module named
'saipen_engine.goal_authority'`), and after copying `goal_authority.py` in it
fails on `REGISTRY.json` lacking the `goal_authority` object that the live
`REGISTRY.json` supplies.

### The 1 host-smoke failure

    test_opencode_host_smoke.OpenCodeRealInstalledGeneration.test_fresh_process_loads_the_installed_generation_from_one_origin

The test compares the digest of the *installed* OpenCode artifact against
`SHIPPED_ARTIFACT` from the tree it runs in. In the HEAD worktree the installed
artifact reports `8cd91666...` while the HEAD tree ships `fae3eed7...`. The live
tree passes in 5.359 s against its own `SHIPPED_ARTIFACT`. This is therefore not
a HEAD-vs-live code defect but a **generation skew**: the installed host carries
the live tree's newer artifact, so the test fails wherever it is run from an
older revision. It is a test-design portability limit, not a green/red signal
about HEAD's source.

## Scale of the same divergence, measured

Those 6 failures are one symptom of a much larger gap the campaign should
state plainly, because it changes what any HEAD-based baseline can prove:

    live  tools/saipen_engine/*.py   155 modules
    HEAD  tools/saipen_engine/*.py   111 modules
    ------------------------------------------------
    43 modules exist only in the live tree

`comm -13` between HEAD's listing and the live listing names them, including
`goal_authority.py`, `focused_unit.py`, `sandbox_scope.py`,
`verification_cache.py`, `process_tree.py`, `host_authority_*.py` (four
modules), `machine_runtime.py` and `readiness.py`. Several are modules this
very campaign relies on: `focused_unit.py` is the focused-evidence gate T-1901
shipped through, and `sandbox_scope.py` is the T-1889 selective-copy
optimization verified in Wave 11.

So "the committed revision" and "the tree the campaign is running in" are not
the same program. Any conclusion drawn by running a family against HEAD
describes a 111-module engine missing 43 modules of decided behaviour, and any
conclusion drawn in the live tree describes a 155-module engine whose repair
work is uncommitted. Both are true statements about different things; neither
substitutes for the other, and the 25-remaining-red free claim cannot be made
from either until publication lands.

This is the mechanical reason publication is not bookkeeping. `T-1815` and the
`release:shared-index` group are blocked because 206 foreign staged paths would
enter the release; behind that gate sit 31 tickets already closed with
`publication_state: pending`. Until those land, the gap above stays open.

## What this changes, and what it does not

- The live-tree 55-red baseline is still explained by the foreign in-flight
  batch: the 6 legacy rows are **not** in that 55, because the live tree already
  holds their fix.
- The claim "0 regressions in shipped code" is still **wrong as written**. 6
  real failures exist at HEAD, and their repair exists only as uncommitted
  work. Until that work lands, a fresh clone of the committed revision fails
  those 6 tests. That is the honest state.
- No source file, baseline file, or foreign dirty file was modified to produce
  this measurement. The only artifacts are this file and the throwaway
  worktree at `V:/_TEMP_/t1882-wt`.

## Reproduce

    git worktree add --detach /tmp/t1882-wt HEAD
    cd /tmp/t1882-wt/tools
    python -B -m unittest test_legacy_lifecycle_compat -v   # 6 failures
    python -B -m unittest test_opencode_host_smoke -v       # 1 failure
    # live tree, same commands:
    cd <project>/tools
    python -B -m unittest test_legacy_lifecycle_compat -v   # OK, 27 tests
