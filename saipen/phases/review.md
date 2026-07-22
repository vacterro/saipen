# Phase: REVIEW

## REVIEW -- is it well made?

`.saipen/extensions/performance/` (or legacy root `extensions/performance/`) present? Read it first -- its README states the
benchmarks/thresholds this repo requires before SHIP (RFC § 1.9). Absent:
skip, no overhead.

On wave/ship diff (`git diff main...` or files changed since STATE.updated).
Prove suspicions with trace/repro. Findings = file:line + what breaks.

- **P0 correctness** -- broken logic, unhandled paths, off-by-one, races, data loss.
- **P1 security** -- string SQL, shell=True, eval, HTML injection, hardcoded secrets
  (-> env var, tell user to rotate), missing authz, weak hashing.
- **P2 reliability** -- silent catches, missing timeouts, leaks, unbounded growth.
- **P3** -- duplication 3+, dead code, missing tests.

P0/P1: fix now (STATE -> BUILD). P2/P3: new tickets.
Verdict -> LOG: `DEC: SHIP` / `SHIP after FIXES` / `NO -- BLOCKER`.
**Cap: 2 review passes per finding (RFC § 2.4), identified by its `file:line`
-- pass 1 finds it, BUILD fixes it, pass 2 re-checks. Still broken on pass 2
-> verdict MUST become `NO -- BLOCKER`, ticket it under `## BLOCKED`, stop cycling on THIS
finding, and transition to the next workable ticket (STATE -> `SCOUT` or `BUILD`). A NEW finding uncovered by the fix itself starts its own fresh
2-pass count -- this caps re-litigating the same finding, not REVIEW as a
whole.**

If P0/P1 clear: STATE -> SHIP. There is no
"STATE -> DONE" branch here -- SHIP is mandatory before DONE, even for a
two-line bugfix, even under `goal_mode`.
