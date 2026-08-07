# Phase: REVIEW

## REVIEW -- is it well made?

`mode: manual-verify` (CORE.md §1.3, no shell on this host)? MUST NOT auto-transition to SHIP. Ask the user for a manual review verdict before proceeding.

`.saipen/extensions/performance/` (or legacy root `extensions/performance/`) present? Read it first -- its README states the
benchmarks/thresholds this repo requires before SHIP (CORE.md §1.9). Absent:
skip, no overhead.

On wave/ship diff (`git diff main...` or files changed since STATE.updated).
Prove suspicions with trace/repro. Findings = file:line + what breaks.

**Re-run the ticket's own `verify:` here; do not read VERIFY's claim of
it.** The evaluator repeats the mandatory check itself, because a phase
that reports on its own work is the one report nothing downstream can
contradict -- and a green claim otherwise carries straight into SHIP on
the strength of the phase that made it. LOG the result of the run you
actually performed. Disagrees with VERIFY's recorded result? That IS the
finding: the tree changed under it, or the claim was never true. Same
check, run twice, is the cheapest independence available to a protocol
with one agent in the seat -- no second agent, no risk tiers, no new
phase. Observed at E-1867: VERIFY reported green and the audit harness
was red on the same tree.

- **P0 correctness** -- broken logic, unhandled paths, off-by-one, races, data loss.
- **P1 security** -- string SQL, shell=True, eval, HTML injection, hardcoded secrets
  (-> env var, tell user to rotate), missing authz, weak hashing.
- **P2 reliability** -- silent catches, missing timeouts, leaks, unbounded growth.
- **P3** -- duplication 3+, dead code, missing tests.

P0/P1: fix now (STATE -> BUILD). P2/P3: new tickets.
Verdict -> LOG: `DEC: SHIP` / `SHIP after FIXES` / `NO -- BLOCKER`.
**Cap: 2 review passes per finding (MAINTENANCE.md §2.4), identified by its `file:line`
-- pass 1 finds it, BUILD fixes it, pass 2 re-checks. Still broken on pass 2
-> verdict MUST become `NO -- BLOCKER`, ticket it under `## BLOCKED`, stop cycling on THIS
finding, and transition to the next workable ticket (STATE -> `SCOUT` or `BUILD`). A NEW finding uncovered by the fix itself starts its own fresh
2-pass count -- this caps re-litigating the same finding, not REVIEW as a
whole.**

If P0/P1 clear: STATE -> SHIP. There is no
"STATE -> DONE" branch here -- SHIP is mandatory before DONE, even for a
two-line bugfix, even under `goal_mode`.

**The passed ticket stays in `## DOING` through SHIP -- do NOT close it
here.** The push has not happened; the work is not done, so `## DONE`
would be a lie. `PHASE SHIP T-###` is the legal `next_action` this phase
emits, and the Pick Rule accepts it precisely because a claimed `## DOING`
ticket IS the pick (CORE.md §1.11): the validator reads `PHASE SHIP T-###`
as naming the in-flight pick, not as a finished ticket. Closing the
ticket at REVIEW was this repository's habit (E-1879, T-466) and it made
§ 1.2's own `PHASE` form unusable for the one phase it names a ticket
for -- the ticket reached `## DONE` while nothing was pushed, so the pick
check rejected `PHASE SHIP T-###` twice over. The ticket moves to
`## DONE` only at the DONE phase, after the push lands
(`phases/done.md`, `phases/ship.md`).
