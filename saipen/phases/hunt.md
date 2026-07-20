# Phase: HUNT (board empty/done)

Clean sweep. Skip only if LOG has `hunt -> clean @HASH` matching current HEAD.

**Subagents available (RFC § 1.3)?** Dispatch the 6 signal categories below
as one batch of parallel subagent tasks instead of scanning them in turn.
Each subagent is read-only: it investigates and returns findings, it MUST
NOT touch `.saipen/` itself -- only the orchestrating agent writes BOARD/LOG,
once, after merging every subagent's results. This avoids write races by
construction. No subagent support -> run the same 6 categories sequentially,
exactly as below. Either path, the cap and output are identical.

Signal order, cap 5 tickets:
1. Failing tests
2. Commits unverified in LOG
3. Stale TODO/FIXME/HACK
4. Silent failures (empty catch, ignored returns, missing IO error paths)
5. Symmetry gaps (save/load, undo/redo, import/export, start/stop)
6. Dead code, orphan files (zero grep refs, not entry/doc/config)

Obvious junk -> delete free. Ambiguous -> ticket + user confirms.
Findings ticketed (not clean)? STATE -> `PLAN` (or straight to `SCOUT` if
a finding is small/obvious enough to skip planning, same judgment call as
`phases/plan.md`'s size gate) -- work them same as any other `TODO`, board
order = priority.
Nothing found -> LOG exactly `RUN: hunt -> clean @SHORT-HASH` (this exact
format, not a free-text summary), then immediately transition to `ADD`.
This transition is unconditional -- a clean hunt is never itself a reason
to stop, under `goal_mode` or otherwise (RFC § 2.4). Never invent busywork.

## Perf (user asks specifically, or a ticket calls for it)

Baseline number first (profiler/timer/EXPLAIN -> LOG).
Fix top proven bottleneck -> re-measure same way.
Gain under 20% and uglier -> revert + LOG why.