# Phase: VERIFY

If .saipen/extensions/security/ (or
legacy extensions/security/) exists, read its required scanners/constraints
first (CORE §1.9).

Under mode: manual-verify, never auto-transition. Ask the human to run verify:
and report the result; record:
next_action: WAIT: manual-verify -- run '<verify: command>' and report pass or fail
Proceed only from that result.

## Verification

Strongest repository harness, cheapest-first: parse -> import -> unit -> repro
-> smoke. First failed mandatory gate: this pass cannot claim PASS;
later green cannot override it.
Only repository/ticket-declared advisory gates are non-blocking; unclassified
means mandatory.

Read the project's canonical commands from `KNOWLEDGE/` (SCOUT records once);
absent: derive from build/CI. Still unknown: WAIT: blocked naming the missing command, no invented
harness. BOARD verify: is minimum: execute/prove it with the strongest applicable
harness; LOG how. Before commands: CORE destructive-effect confirmation and
OPS-EFFECT-01; BOARD grants no authority. Manual-verify gives the human that
same command.

- Nontrivial new logic needs a repository-style test.
- Bug fixes need the SAME regression test, fixture, oracle and configuration:
  pre-fix red, post-fix green; only implementation changes (VERIFY-ORACLE-01).
- Unavailable GUI/environment checks: LOG MANUAL-VERIFY STEPS + EXPECTED;
  never fabricate PASS. Steps cannot satisfy VERIFY. A separate verdict event
  must BEGIN MANUAL-VERIFY RESULT: PASS or MANUAL-VERIFY RESULT: FAIL, only
  from the human's actual report; mentioning the markers grants no verdict.
- End conf: high for green tests, med for smoke only, low for manual evidence.

### Proportional ticket checks

Full-family reruns consume small-edit loops. Opt-in
tools/verification_policy.json permits:
python tools/core_unit.py focused T-### --pattern test_name.py
Repeat --pattern for affected direct consumers, selecting the regression and
contract/failure paths from the owned diff. The isolated current-tree record
rejects zero tests/reds; the entire local run is limited to 300 seconds and
proves only its selection. REVIEW checks selection/delta, reuses unchanged evidence. Further runs need
changed subject, failure or uncovered hypothesis. Over budget: split Work or
explicit full family; never omit required coverage.

Static import edges do not prove dependency completeness.
python tools/core_unit.py impact T-### --plan reports a generation-bound Git
delta plan; repeat --changed PATH for explicit scope. Planning executes nothing.
Without --plan, only a certified static subset executes through existing
discovery/shards. Unknown dependencies/safety boundaries require FULL, with no
narrow citation. Import failures remain selected. Actual IMPACT retains the
focused family, exact manifest/configuration; never full publication evidence.
Manual FOCUSED retains its reviewed-scope contract. Other families and RELEASE
gates remain independent.

Run the complete family once on the finished publication batch after its last
content/metadata edit; publication and CI still require it. Pending cohort
closure collects related verified tickets (phases/ship.md). Regression/oracle
and acceptance gates remain mandatory. No policy: retain the existing full gate.

### Instrument controls

<!-- RULE-OWNER: VERIFY-ORACLE-01 -->

New/inherited gates need demonstrated known-bad red. Zero tests, missing
targets, continue-on-error/allow_failure, || true and self-caught failures are
UNVERIFIED. LOG actual run AND deliberate red control for conf: high.

Known-good control before broad negatives. Failure means verifier unavailability,
not subject failure: repair it. Pin verifier versions/explicit rules;
unpinned defaults can change verdicts for identical bytes.

For fixes, the known-bad input is the PRE-FIX SUBJECT. Restore its bug without
changing the test and prove red again; a still-green regression proves neither
defect nor fix. Declare regression: required on BOARD (prose cannot classify
bug-fix authority), with anchored records:

REGRESSION-EVIDENCE FAIL verifier:<hex> subject:<hex> -- <what ran>
REGRESSION-EVIDENCE PASS verifier:<hex> subject:<hex> -- <what ran>

VERIFY -> REVIEW and atomic finish consume
saipen_engine.oracle.regression_pair_verdict: only ADMISSIBLE passes.
Missing half: NO_REGRESSION_EVIDENCE; weaker/changed oracle: ORACLE_CHANGED.
Describing a record is not anchoring it. Work without the field is untouched.

### Declared acceptance preservation (SRC-216)

Native REVIEW/finish enforce AC-NN [WITNESS] outcome through acceptance_contract;
ordinary PASS never waives criteria. ticket verify preserves full preimages.
Deletion, redefinition or weaker witnesses require OPS §13's exact operator
amendment AND independently proven replacements at no weaker floor. Equivalent
implementation changes need none; legacy untyped Work gains no LIVE proof.

LIVE/MANUAL AC-EVIDENCE requires source=SRC-N: immutable operator observation
bound to Work, full contract digest, latest BUILD, criterion/result/witness/
surface. It proves the human report, not automated observation. Model prose or
a stronger retry cannot authenticate it. Missing/weak/stale/contested inputs
refuse without writes. Typed supersession preserves independently satisfied
equivalent criteria; dedicated authority/completion gates remain due.

### Active execution (SRC-212)

Without regression_evidence: executed, evidence is legacy attestation.
ticket regression ... --evidence executed strengthens it; never downgrade.
work regression ... --file measures owned VERIFY Work: atomic pair/receipt/
profile, unchanged phase.

Closed schema:
```json
{"schema":1,"command":["node","--test","--test-reporter=tap","control.cjs"],
 "format":"tap","context":["subject.cjs","control.cjs"],
 "oracle_files":["control.cjs"],"subject_files":["subject.cjs"],
 "before":{"subject.cjs":".saipen/evidence/pre/subject.cjs"},"timeout":60}
```

Context: all dependencies/config/owned inputs, disjoint oracle/subject.
Before material: evidence (null=absent). Refuse links/root memory/Git.
Timeout: 1..5400s; native argv; {python} selects Python.
Formats: unittest, pytest, tap, playwright-json; pin reporters
(--reporter=json for Playwright). One runtime/environment/oracle, completed
FAIL/exit1 before and PASS/exit0 after. Startup/timeout/zero tests refuse;
reap descendants. REVIEW/finish recheck committed carrier integrity, Work/lineage/Source/
acceptance, cycle/Attempt/inputs: forged/changed/stale refuse. Replay grants no
authority. Dry-run executes/writes nothing; read-only refuses. Other checks
remain due; copies claim no sandbox.

Changing the verifier is allowed; tests are not frozen during a fix. Any test, fixture, expectation,
mock, seed, tolerance, golden, discovery pattern, timeout or command change
invalidates old evidence: record why on its evidence, give the new oracle
its own red control and re-establish pre-fix FAIL. Old FAIL plus new-oracle PASS is not a pair.
Changing implementation and test together refuses because attribution
is lost. oracle.py decides arithmetic; digests prove identity, not correctness:
both identity and red control are required.

## Failure and retry

Reproduce exactly; quote the decisive error. Check cheap suspects, LOG each
hypothesis/test and fix the cause. CORE PHASE-DELTA-01 forbids retry without
changed evidence/input/environment/hypothesis.

Cap: 3 dead hypotheses OR 2 failed fix cycles -> block. Each failed cycle
increments | verify_attempts: N (absent=0). At cap, canonical ticket block
moves Work to ## BLOCKED and sets | blocker:. Preserve attempts in BOARD/LOG.
ticket unblock needs the lifting decision, removes blocker, resets the current
attempt budget; identical retries stay forbidden.

Another workable TODO: keep this Work blocked, route to its SCOUT/BUILD.
None: session BLOCKED with concrete WAIT: (phases/blocked.md).

Before switching tickets, preserve/remove ONLY this failed attempt's partial
edits. With Git: save git diff to .saipen/kitchen/failed/T-###.patch, restore
only owned tracked paths, move only proven attempt-created untracked files
beside it. Never blanket git clean or disturb unrelated dirt; record mid-attempt
commits in the blocker. Without Git: copy edited files to that bounded kitchen
and state that partial changes remain in the tree. Recovery is reversible;
generic authorization/checkpoints remain CORE/OPS.

## Exit and evidence

PASS needs the ticket check, applicable harness/regressions, both required
instrument controls, LOGged commands/results and confidence. Then
REVIEW, never next ticket.

For execution_intent: goal, this unique accounting point increments
goal_tickets once per pass and writes DEC: goal_tickets N->M before checkpoint.
Persistence/20-ticket cap/stop/reauthorization: MAINTENANCE §2.4.
