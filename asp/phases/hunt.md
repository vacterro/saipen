# Phase: HUNT (board empty/done)

Clean sweep. Skip only if LOG has `hunt -> clean @HASH` matching current HEAD.

Signal order, cap 5 tickets:
1. Failing tests
2. Commits unverified in LOG
3. Stale TODO/FIXME/HACK
4. Silent failures (empty catch, ignored returns, missing IO error paths)
5. Symmetry gaps (save/load, undo/redo, import/export, start/stop)
6. Dead code, orphan files (zero grep refs, not entry/doc/config)

Obvious junk -> delete free. Ambiguous -> ticket + user confirms.
Nothing found -> `RUN: hunt -> clean @SHORT-HASH`, report, stop.
Never invent busywork.

## Perf (perf flag)

Baseline number first (profiler/timer/EXPLAIN -> LOG).
Fix top proven bottleneck -> re-measure same way.
Gain under 20% and uglier -> revert + LOG why.