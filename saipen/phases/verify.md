# Phase: VERIFY

## VERIFY -- does it work?

`.saipen/extensions/security/` (or legacy root `extensions/security/`) present? Read it first -- its README states the
scanners/constraints this repo requires before REVIEW (RFC § 1.9). Absent:
skip, no overhead.

`mode: manual-verify` (RFC § 1.3, no shell on this host)? MUST NOT
auto-transition to REVIEW. Ask the user to run the `verify:` command
themselves and report the result: `next_action: WAIT: run '<verify:
command>' and report pass or fail`. Proceed only once they confirm.

Repo's own harness only (never invent one). Strongest available:
parse -> import -> unit -> repro -> smoke.
`verify:` is the minimum. LOG every result.
New nontrivial logic -> repo-style test.
Fixed bug -> regression test that failed pre-fix.
GUI/env unverifiable -> LOG `MANUAL-VERIFY STEPS + EXPECTED`, never fake.
Close with `conf:` -- high (tests green), med (smoke only), low (manual).

## Debug (on FAIL)

Reproduce exactly, quote decisive error line.
Cheap suspects first (git log, config, env, named file).
Hypothesis -> LOG -> test -> fix root cause, not symptom.
Rejected hypotheses stay logged; never re-test without new evidence.
**Cap: 3 dead hypotheses OR 2 failed fix cycles -> move THIS ticket to the
`## BLOCKED` section on `BOARD.md` with the facts + dead ends noted on it,
then check for another unblocked `TODO` ticket and work that instead (STATE -> `SCOUT` or `BUILD`).**
`STATE.phase: BLOCKED` (which loads
`phases/blocked.md` and stops for the user) is reserved for when no other
ticket on the board is workable -- one stuck ticket MUST NOT halt a session
that still has other work available, under `goal_mode` or otherwise.

**Clean tree before the next ticket.** A blocked ticket MUST NOT leave its
half-broken edits sitting in the working tree -- the next ticket would
build on contaminated code and every later verify inherits the mess.
Before picking the next ticket:
- Git available: save the failed attempt first -- `git diff >
  .saipen/kitchen/failed/T-###.patch` -- then revert the failed ticket's
  uncommitted changes (`git restore <files>`). Nothing is lost: the patch
  re-applies with `git apply` if the ticket comes back, and it auto-clears
  under kitchen's stale rule once the ticket is done or pruned. This
  revert is pre-authorized by this procedure and reversible via the saved
  patch, satisfying RFC § 1.1's destructive-op rule. Changes already
  committed mid-attempt stay in history -- note the commit hash in the
  ticket's `| blocker:` field instead.
- No git (degraded mode): copy this attempt's edited files to
  `.saipen/kitchen/failed/T-###/` and state plainly in `| blocker:` that
  the tree still carries partial changes -- never silently pretend the
  tree is clean when it isn't.

After VERIFY pass: STATE -> REVIEW. There is no 'next ticket' branch here -- `REVIEW` and `SHIP` are mandatory for the current ticket before picking up another.
`goal_mode: true`? Increment `goal_tickets` by 1 and checkpoint STATE
(RFC § 2.4). That hits the 3-`goal_waves`/20-`goal_tickets` cap? STOP here
instead of continuing -- full BOARD/STATE checkpoint, report progress, wait
for the user to re-invoke `saipen goal`.
