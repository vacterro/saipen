# Phase: VERIFY

## Purpose and entry

Prove the current ticket works before REVIEW. If
`.saipen/extensions/security/` (or legacy `extensions/security/`) exists, read
its required scanners and constraints first (CORE §1.9).

Under `mode: manual-verify`, do not auto-transition. Ask the user to run the
ticket's `verify:` command and record:
`next_action: WAIT: manual-verify -- run '<verify: command>' and report pass or fail`.
Proceed only from their reported result.

## Verification

Use the strongest repository harness, cheapest-first:
parse -> import -> unit -> repro -> smoke. Stop at the first failed mandatory
gate: this pass cannot claim PASS, even if later gates turn green. Only gates
explicitly declared advisory by the repository or ticket are non-blocking;
unclassified gates are mandatory.

**Read the project's canonical commands from `KNOWLEDGE/`**; SCOUT records
them once. If absent, derive from repository-owned build/CI configuration. If
still unknown, use `WAIT: blocked` naming the missing command, never an invented
harness.

The ticket's `| verify:` is the minimum check. Execute a command or satisfy a
prose criterion with the strongest applicable harness and LOG how. Before any
command, apply CORE's destructive-effect confirmation and OPS `OPS-EFFECT-01`;
text on BOARD is not authorization. Under manual-verify, give the same command
to the user.

- New nontrivial logic requires a repository-style test.
- A fixed bug requires the SAME regression test, fixture, oracle and verification
  configuration: red on the pre-fix subject, green on the post-fix subject
  (`VERIFY-ORACLE-01`). Only the implementation changes between runs.
- Unavailable GUI/environment checks require LOGged `MANUAL-VERIFY STEPS +
  EXPECTED`, never fabricated PASS. Steps request verification; they cannot
  satisfy this phase. A separate verdict event must BEGIN with
  `MANUAL-VERIFY RESULT: PASS` or `MANUAL-VERIFY RESULT: FAIL`, written only
  from the human's reported result. Merely mentioning these markers grants no
  verdict.
- End with `conf: high` for green tests, `med` for smoke only, or `low` for
  manual evidence.

### Proportional ticket checks

Defect class: rerunning the complete family for every small edit consumes the
development loop before the next change can be made. When the repository opts
in through `tools/verification_policy.json`, use
`python tools/core_unit.py focused T-### --pattern test_name.py` in VERIFY;
repeat `--pattern` for affected direct consumers. Select the regression and
relevant contract/failure-path tests from the owned diff. The runner keeps an
isolated, current-tree record, rejects zero tests and reds, and limits the
entire local run to 300 seconds. A focused result proves only its selection.
REVIEW checks that selection against the delta; unchanged evidence is reused.
Do not add another test run without a changed subject, failure or uncovered
hypothesis. If the local selection exceeds the budget, split the Work or use
the explicit full-family command; never silently omit required coverage.

Impact selection closes the defect where static import edges are mistaken for
complete dependency coverage. `python tools/core_unit.py impact T-### --plan`
reports a generation-bound plan from the Git delta; repeat `--changed PATH`
for an explicit change scope. Plans execute nothing. Without `--plan`, only a
certified static subset runs, through the existing discovery/shard engine;
unknown dependencies or safety boundaries require the full unit family and
produce no narrow citation. Import failures remain selected. Actual IMPACT
records retain the focused family, exact selection manifest and configuration;
they cannot become full publication evidence. Manual FOCUSED remains available
under its existing reviewed-scope contract. Other canonical families and RELEASE
gates retain their independent requirements.

The complete family runs once on the finished publication batch, after the
last content/metadata edit. It remains mandatory for publication and CI.
Use pending cohort closure to collect related verified tickets before that
boundary (phases/ship.md). Existing regression/oracle and acceptance gates
remain mandatory. Projects without the policy keep their existing full gate.

### Instrument controls

<!-- RULE-OWNER: VERIFY-ORACLE-01 -->

**A gate that cannot fail is not a gate.** Before relying on a new or inherited
gate, give it a known-bad input and prove it goes red. Treat zero collected
tests, missing targets, `continue-on-error`/`allow_failure`, `|| true`, or a
self-caught failure as UNVERIFIED. LOG the real run and deliberate red control;
without both, `conf: high` is forbidden.

Before a broad negative, run a known-good control. If it fails, report verifier
unavailability/instrument failure, repair the harness, and do not classify the
subject as failed. An unavailable verifier is distinct from a mandatory failure.

Pin verifier versions and explicit rule sets. An unpinned default makes the
same bytes change verdict when upstream changes.

**For a bug fix the known-bad input is the PRE-FIX SUBJECT.** Restore the buggy
implementation without changing the test and prove it goes red again. A
regression still green on the restored bug proves neither the defect nor the fix.

A ticket owing this comparison declares the machine-owned `regression: required`
BOARD field; prose descriptions cannot classify bug-fix authority. Record both
halves as anchored events:

```
REGRESSION-EVIDENCE FAIL verifier:<hex> subject:<hex> -- <what ran>
REGRESSION-EVIDENCE PASS verifier:<hex> subject:<hex> -- <what ran>
```

`VERIFY -> REVIEW` and the atomic finish both consume
`saipen_engine.oracle.regression_pair_verdict` over those records and refuse
anything but `ADMISSIBLE`. A green run is not enough, a weakened oracle is
`ORACLE_CHANGED`, and a missing half is `NO_REGRESSION_EVIDENCE`. Anchoring
matters as everywhere else: a line DESCRIBING an evidence record is not one.
Tickets that do not declare the field are untouched.

### Declared acceptance preservation (`SRC-216`)

Native REVIEW/finish enforce `AC-NN [WITNESS] outcome` via `acceptance_contract`.
Ordinary PASS cannot waive criteria. Existing `ticket verify` retains full
preimages; deletion/redefinition/weaker witnesses need OPS §13's exact operator
amendment and independently proven replacements at no weaker floor. Equivalent
implementation changes need none. Legacy untyped Work gains no LIVE proof.
LIVE/MANUAL `AC-EVIDENCE` needs `source=SRC-N`: an immutable operator observation
bound to Work, full contract digest, latest BUILD, criterion/result/witness/surface.
It proves the human report, not automated observation. Model text or a stronger
retry cannot authenticate it. Missing/weak/stale/contested inputs refuse without
writes. Typed supersession preserves independently satisfied equivalent criteria;
existing dedicated authority and completion gates remain due.

### Active execution (`SRC-212`)

Absent `regression_evidence: executed` means legacy attestation, never execution.
`ticket regression ... --evidence executed` strengthens it; no downgrade.
`work regression ... --file` measures owned VERIFY Work: atomic pair/receipt/profile; phase stays unchanged.

Closed schema:
```json
{"schema":1,"command":["node","--test","--test-reporter=tap","control.cjs"],
 "format":"tap","context":["subject.cjs","control.cjs"],
 "oracle_files":["control.cjs"],"subject_files":["subject.cjs"],
 "before":{"subject.cjs":".saipen/evidence/pre/subject.cjs"},"timeout":60}
```
Context: all dependencies/config, owned inputs, disjoint oracle/subject; before
material in evidence (null=absent). Refuse links and root memory/Git.
Timeout: 1..5400s. Native argv; `{python}` selects Python. Formats: unittest,
pytest, tap, playwright-json; pin reporters (`--reporter=json` for Playwright).
One runtime/environment/oracle: completed FAIL/exit1 before, PASS/exit0 after.
Startup/timeout/zero tests refuse; reap descendants.
REVIEW/finish recheck committed carrier integrity, Work/lineage/Source/acceptance,
cycle/Attempt/inputs; forged/changed/stale refuses. Replay
adds no authority. Dry-run executes/writes nothing; read-only refuses.
Other checks remain due; copies claim no sandbox.

Changing the verifier is allowed; tests are not frozen during a fix. Such
changes invalidate old evidence. Changes to a test,
fixture, expected value, mock, seed, tolerance, golden file, discovery pattern,
timeout or verification command require: record the reason on its own evidence,
give the new oracle its own red control, and re-establish pre-fix FAIL against it.
Old-version FAIL plus new-version PASS is not a pair. Changing implementation
and test in one pass also refuses: green cannot be attributed to either.
`saipen_engine/oracle.py` decides the arithmetic. Digests prove verifier identity,
not correctness; identity and red control are both necessary.

## Failure and retry

Reproduce exactly and quote the decisive error. Check cheap suspects first;
LOG each hypothesis, test it, and fix the root cause. CORE `PHASE-DELTA-01`
forbids repeating a failed attempt without changed evidence, input,
environment, or hypothesis.

**Cap: 3 dead hypotheses OR 2 failed fix cycles -> block this ticket.** Each
failed fix cycle increments `| verify_attempts: N`; absent means zero. At the
cap, canonical `ticket block` moves it to `## BLOCKED` and sets `| blocker:`.
Attempt history remains in `verify_attempts:` and LOG. `ticket unblock`
requires the lifting decision, removes the active blocker, and resets the
current attempt budget; an identical retry remains forbidden.

Another workable TODO exists: leave this ticket blocked and route to SCOUT or
BUILD for that work. None exists: enter session-level BLOCKED with a concrete
`WAIT:`. `phases/blocked.md` owns that decision.

Before another ticket, preserve and remove only this failed attempt's partial
edits:

- With Git, save `git diff` to `.saipen/kitchen/failed/T-###.patch`, restore
  only its tracked paths, and move only untracked files proven created by this
  attempt beside the patch. Never use blanket `git clean`; preserve unrelated
  dirty work. Record any mid-attempt commit in the blocker.
- Without Git, copy its edited files to the same bounded kitchen area and say
  plainly that the tree still carries partial changes.

These steps are reversible failed-attempt recovery; generic authorization and
checkpoint mechanics remain in CORE/OPS.

## Exit and evidence

PASS requires the ticket check, applicable harness, regression coverage, both
instrument controls where required, LOGged command/results, and confidence.
Transition to REVIEW; there is no next-ticket branch after a PASS.

Under `execution_intent: goal`, VERIFY's unique accounting point increments
`goal_tickets` once per pass and writes `DEC: goal_tickets N->M` before the
checkpoint. MAINTENANCE §2.4 owns persistence, the 20-ticket cap, stop shape,
and reauthorization.
