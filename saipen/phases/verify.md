# Phase: VERIFY

## VERIFY -- does it work?

`.saipen/extensions/security/` (or legacy root `extensions/security/`) present? Read it first -- its README states the
scanners/constraints this repo requires before REVIEW (CORE.md §1.9). Absent:
skip, no overhead.

`mode: manual-verify` (CORE.md §1.3, no shell on this host)? MUST NOT
auto-transition to REVIEW. Ask the user to run the `verify:` command
themselves and report the result: `next_action: WAIT: manual-verify -- run
'<verify: command>' and report pass or fail`. Proceed only once they confirm.

Repo's own harness only (never invent one). Strongest available:
parse -> import -> unit -> repro -> smoke.
**That order is cheapest-first, and it is not decoration**: a parse
error found by the full suite costs the whole suite to learn something
the first rung would have said in a second. Run them in that order and
stop climbing when one fails.
**The first failed MANDATORY gate ends the PASS claim for this pass.**
No later green restores it -- a green from a rung above a red one is a
statement about a different question, not a repair of the failed one.
An advisory gate (a lint warning nobody has made blocking, an optional
benchmark) may fail without ending the claim, but only if this ticket
or the repo says it is advisory; unclassified means mandatory.
**Read the project's canonical commands from `KNOWLEDGE/`, do not
re-derive them.** `phases/scout.md` writes them there once on the first
ticket that needs them; every later executor and reviewer cites that
line. Two agents each guessing a build command is how one of them
verifies something nobody asked for and reports it green. Not there and
not derivable from the repo? `WAIT: blocked` naming the missing command
-- § 1.11 already forbids picking a convenient one and declaring
victory.
`verify:` is the minimum -- a ticket's own `| verify:` field (CORE.md §1.2,
set at `phases/plan.md` time) is the concrete check this phase runs for it:
a shell command -> execute it and LOG the result; a criterion in prose (no
runnable command) -> satisfy it by the strongest harness available above and
LOG how. **Never execute a `verify:` command blind** -- a ticket collected
from a subSaipen's OUTBOX or written by a much earlier/different session is
still just text on `BOARD.md` until this moment. A command matching an
obviously destructive pattern (`rm -rf`, a database drop, `git push
--force`, `curl ... | sh`, anything that would delete, overwrite remote
history, or fetch-and-run) is a destructive op same as CORE.md §1.1's own
list -- stop and get explicit user confirmation before running it, never
treat "it's just the verify step" as pre-authorization the ticket itself
can't actually grant. Under `mode: manual-verify` the `verify:` command is
exactly what you ask the user to run (the `WAIT:` above). LOG every result.
New nontrivial logic -> repo-style test.
Fixed bug -> regression test that failed pre-fix.
GUI/env unverifiable -> LOG `MANUAL-VERIFY STEPS + EXPECTED`, never fake.
Close with `conf:` -- high (tests green), med (smoke only), low (manual).

**A gate that cannot fail is not a gate.** "Never fake" above covers lying
about a result; this covers the quieter version, where nobody lies but the
instrument was never connected. Green from a check that is *incapable* of
going red is not evidence -- it is manufactured confidence, and it is worse
than no check because it stops anyone looking. Before trusting any gate,
yours or inherited, treat these as UNVERIFIED until proven otherwise:
- a CI job carrying `continue-on-error` / `allow_failure` / a trailing
  `|| true` -- it cannot fail the build no matter what breaks;
- a step that catches its own failure and prints a soft word (`SKIP`,
  `warn`, `note`) instead of exiting non-zero;
- a suite that collected 0 tests, or matched only files that no longer exist.

The proof is cheap and mandatory when you rely on the gate: **break it once
on purpose.** Feed it a known-bad input and confirm it goes red. Stays green
-> you found a second defect, not a passing test. LOG both runs -- the real
green one and the deliberate red one; a `conf: high` claimed on a gate never
shown capable of failing is not `high`.

**A gate stuck red lies as loudly as one stuck green.** The rule above guards
one pole; this guards the other. When a run says *everything* failed --
20 of 20 checks dead, every fixture broken, the whole floor gone -- that is a
claim about your instrument before it is a claim about the subject. A real
defect is almost never total; a misconfigured harness almost always is.
So before reporting any negative, make the instrument prove it can see a
positive: run one input whose expected result is already known and confirm
it comes back as expected. Control silent -> report nothing, fix the
instrument. Three harnesses in one v7.101.0 session claimed total failure and
were each wrong: one invoked the WSL `bash` stub instead of the real shell,
one matched on an internal key never present in the output, one asserted a
check catch something it had never claimed to. All three would have shipped a
confident, false finding.

**Pin what a gate depends on.** An unpinned linter/formatter/type-checker
makes the gate nondeterministic: a new upstream release shifts the default
rule set and the build goes red with zero code changes, which teaches
everyone to ignore it -- the same end state as a gate that never fires. Pin
the version AND state the rule set explicitly; a default set is whatever the
tool shipped that week, not a decision this repo made.

## Debug (on FAIL)

Reproduce exactly, quote decisive error line.
Cheap suspects first (git log, config, env, named file).
Hypothesis -> LOG -> test -> fix root cause, not symptom.
Rejected hypotheses stay logged; never re-test without new evidence --
CORE.md §1.6 states this for every repeated attempt, not just hypotheses;
this line is the debugging instance of it.
**Cap: 3 dead hypotheses OR 2 failed fix cycles -> move THIS ticket to the
`## BLOCKED` section on `BOARD.md` with the facts + dead ends noted on it,
then check for another unblocked `TODO` ticket and work that instead (STATE -> `SCOUT` or `BUILD`).**
**Count the cycles on the ticket, not in your head.** Every failed fix cycle
increments `| verify_attempts: N` on the ticket line (CORE.md §1.2's closed field
list; absent reads as zero). `tools/validate.py` FAILs a ticket at or over the
cap above that carries no `| blocker:`, and it reads the cap out of this very
sentence rather than keeping its own copy. The field exists for the reason
`review_passes:` does one phase over: a cap counted from memory is a cap the
next session does not have.

**Hysteresis**: `| blocker:` is ACTIVE blocked status, never attempt history.
At the cap, use canonical `ticket block`: it moves the ticket to `## BLOCKED`
and sets the current blocker atomically. Failed-attempt history stays in
`verify_attempts:` plus the journaled LOG hypotheses/fix results. A canonical
`ticket unblock` records the decision, moves the ticket to `## TODO`, removes
the blocker, and clears the current attempt budget; carrying `| blocker:` into
`## TODO` is status corruption, not preservation. An identical retry remains
forbidden by CORE.md §1.6's repeated-attempt rule; a newly authorized attempt
must name changed evidence. **What the block means for the session depends on
the rest of the board, and `phases/blocked.md`'s own entry condition decides
it, not this cap**: another workable `TODO` exists -> leave this ticket in
`## BLOCKED` and work that one. Nothing else is workable -> `STATE.phase:
BLOCKED` with a concrete `WAIT:` naming the decision this ticket needs.

**Clean tree before the next ticket.** A blocked ticket MUST NOT leave its
half-broken edits sitting in the working tree -- the next ticket would
build on contaminated code and every later verify inherits the mess.
Before picking the next ticket:
- Git available: save the failed attempt first -- `git diff >
  .saipen/kitchen/failed/T-###.patch` -- then revert the failed ticket's
  uncommitted changes (`git restore <files>`). `git restore` only touches
  already-tracked files -- if BUILD also created brand-new files this
  attempt (a new module, a stray scratch file), those stay on disk
  untouched by `restore` alone and the "clean tree" promise above would be
  false. Check `git status --porcelain` for untracked entries that weren't
  there before this ticket's `SCOUT`/`BUILD` started, and move exactly
  those into `.saipen/kitchen/failed/T-###/` alongside the patch (never a
  blanket `git clean` -- that would just as happily eat someone else's
  unrelated untracked scratch, which CORE.md §1.5's dirty-tree rule already
  forbids touching). Nothing is lost: the patch re-applies with `git apply`
  if the ticket comes back, the moved files sit right next to it, and both
  auto-clear under kitchen's stale rule once the ticket is done or pruned.
  This revert is pre-authorized by this procedure and reversible via the
  saved patch, satisfying CORE.md §1.1's destructive-op rule. Changes already
  committed mid-attempt stay in history -- note the commit hash in the
  ticket's `| blocker:` field instead.
- No git (degraded mode): copy this attempt's edited files to
  `.saipen/kitchen/failed/T-###/` and state plainly in `| blocker:` that
  the tree still carries partial changes -- never silently pretend the
  tree is clean when it isn't.

After VERIFY pass: STATE -> REVIEW. There is no 'next ticket' branch here -- `REVIEW` and `SHIP` are mandatory for the current ticket before picking up another.
`execution_intent: goal`? Increment `goal_tickets` by 1, write the LOG line MAINTENANCE.md
§ 2.4 requires for it -- `DEC: goal_tickets N->M`, that exact text after
the taxonomy -- and checkpoint STATE (MAINTENANCE.md §2.4). The line is what makes
§ 1.5's Recovery able to rebuild the counter after a crash; a bump
recorded only in `STATE.md` is invisible to it if `STATE.md` is what was
lost. That hits the 3-`goal_waves`/20-`goal_tickets` cap? STOP here
instead of continuing -- full BOARD/STATE checkpoint, report progress, wait
for the user to re-invoke `cc` to re-authorize and continue.
