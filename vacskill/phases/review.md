# Phase: REVIEW

## REVIEW -- is it well made?

On wave/ship diff (`git diff main...` or files changed since STATE.updated).
Prove suspicions with trace/repro. Findings = file:line + what breaks.

- **P0 correctness** -- broken logic, unhandled paths, off-by-one, races, data loss.
- **P1 security** -- string SQL, shell=True, eval, HTML injection, hardcoded secrets
  (-> env var, tell user to rotate), missing authz, weak hashing.
- **P2 reliability** -- silent catches, missing timeouts, leaks, unbounded growth.
- **P3** -- duplication 3+, dead code, missing tests.

P0/P1: fix now (STATE -> BUILD). P2/P3: new tickets.
Verdict -> LOG: `DEC: SHIP` / `SHIP after FIXES` / `NO -- BLOCKER`.
**Cap: LOG has a verdict on this finding -> NO + ticket, stop cycling.**

If P0/P1 clear and all tickets verified: STATE -> SHIP.
