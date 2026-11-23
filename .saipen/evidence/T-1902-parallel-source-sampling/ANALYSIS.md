# T-1902 — overlap the source-identity sampling reads

## What was slow, measured

`compute_source_identity` runs `_git_identity`, which samples the working tree
three times. Breakdown on the live tree before the change (`git-delta-v1`,
482 content-bearing paths):

    3 × _git_delta_listing          0.117 + 0.131 + 0.132 = 0.380 s
    3 × _parse_git_delta_evidence   0.217 + 0.188 + 0.207 = 0.612 s
    ---------------------------------------------------------------
    _git_identity total                              1.012 s

Every file was read three times, back to back, on one thread. The reads inside
a single pass are independent of each other -- they do not share state and they
cannot observe one another -- so the only reason they were serial was
simplicity.

## What changed

`_parse_git_delta_evidence` gained a `parallel` flag (default on) and a bounded
`ThreadPoolExecutor` over the per-file `_record_evidence` reads. **The pass
structure is untouched**: still three listings, still three parses, still
byte-equality between the three listings and between the three record sets.
Nothing about tolerance changed; this is the same read, overlapped.

Three properties are preserved on purpose, because the stability proof leans on
them and an earlier draft got each one wrong in turn:

1. **The confirming pass stays sequential.** Its frames stream into the
   canonical digest, and `git-delta-v1` is a hash over that frame *sequence*.
   `_git_identity` calls it with `parallel=False` and the docstring says why.
   The alternative implementation -- overlapping it too and hashing sorted
   frames -- would silently redefine the identity of an unchanged tree.

2. **Order is `sorted(records)`, not by kind and not by completion.** The first
   draft sorted merged results by path and hoisted every deletion frame to the
   end. `test_record_order_is_sorted_regardless_of_deletions` and
   `test_parallel_path_does_not_run_when_an_observer_is_present` caught it: the
   observer saw `gone.txt, b.txt, ...` instead of `b.txt, ..., gone.txt`.
   That is a fingerprint change for an unchanged tree, so the observer branch
   now runs the original single loop verbatim, and the parallel machinery only
   ever serves observer-less passes.

3. **`path_map` is filled on the main thread, in sorted order, before any
   worker starts.** No two workers can race for one raw path, and the cache
   contents are identical to the sequential run. Results are collected in
   submission order, so a failing input raises the same `FreshnessError` for the
   same path a sequential pass would have raised first, never whichever worker
   lost a race.

Memory is unchanged: `_record_evidence` returns a content *digest*, so a worker
still never holds more than one file's bytes.

## Measured result, same tree, back to back

`before-after.json` is the raw pair (5 runs each, same process, same tree,
`_READ_WORKERS` flipped between the two):

| | min | median | fingerprint |
| --- | --- | --- | --- |
| sequential (`_READ_WORKERS = 1`) | 0.894 s | **0.970 s** | `git-delta-v1:150f35c4…` |
| parallel (`_READ_WORKERS = 8`) | 0.768 s | **0.793 s** | `git-delta-v1:150f35c4…` |

The fingerprint is identical, which is the point: the optimization is a cost
change, never a semantic one. Median improved 18.2 %, best case 14.1 %.

Per phase, measured with an instrumented run: the two observer-less parses fell
from 0.217 s and 0.188 s to 0.121 s and 0.128 s; the sequential confirming parse
stayed at 0.208 s. That 0.338 s of parse saving is the whole win; the three
listings (0.380 s, a Git subprocess each, T-1900's pathspec already shrank them)
and the confirming parse are untouched by design.

`_READ_WORKERS = 8` rather than 16 on purpose: the measured ceiling is shallow
(4 workers 0.144 s, 8 workers 0.131 s, 16 workers 0.130 s) and the project lives
on a `V:` network volume, where opening 482 handles at once buys nothing.

## Verification

    python -B tools/core_unit.py focused T-1902 \
      --pattern test_t1902_parallel_source_sampling.py \
      --pattern test_t1900_git_listing_boundary.py \
      --pattern test_nested_source_binding.py --timeout 300
    # PASS, 24 ran, 107.593 s
    # record: .saipen/evidence/focused-unit/6188266ad99e628a-20261025T042540440807Z.json

A wider freshness family also ran green in-process: `test_t1900_git_listing_boundary`,
`test_nested_source_binding`, `test_concurrency_independence`,
`test_t1760_no_git_ccc_marker`, `test_t1902_parallel_source_sampling`,
`test_t1511_soak_source_identity` -- 49 tests, `OK (skipped=1)`.

The new file pins five behaviours with no timing assertion anywhere (a duration
assertion on a shared machine is a flaky test; the numbers live in this
document instead):

- parallel and sequential evidence are equal, and their `path_map`s are equal;
- record order stays sorted, with deletions at their sorted position;
- the observer branch is ordered (the confirming-pass contract);
- the whole capture yields the same fingerprint with 1 worker and with 8;
- an unreadable input raises the same error text either way.

## Honest limits

- `continue --json` makes **zero** `compute_source_identity` calls (measured: 0
  calls, 3.143 s wall). The cost lands on journal writes
  (`journal.py:802`), convergence, cold truth and receipt closure. So this win
  is per *mutation*, not per read, and it is 0.18 s per mutation, not per
  keystroke.
- 0.380 s of the remaining 0.793 s is three Git subprocesses. Cutting that
  needs fewer passes or a cheaper listing, and both are stability-proof changes,
  not read changes -- a separate ticket, not a silent extension of this one.
- The confirming parse is 0.208 s of unavoidable sequential work under the
  current framing. Parallelizing it would require a different fingerprint
  scheme, which would move every recorded identity in the project.
