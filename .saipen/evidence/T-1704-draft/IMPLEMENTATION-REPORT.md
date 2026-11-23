# T-1704: continuation correction and legacy authorization transition

Status: engineering validation complete; mission blocked on genuine scoped
operator ingress. This is not a task closure or an
operator-ingress receipt. T-1703 remains the active REVIEW Work at 0 waves / 20
verified tickets. No live persistent grant or counter reset has been made.

## Root cause and existing mechanism

SRC-112 / T-1494 already implements persistent continuation. The live goal is
legacy bounded, with no authority quartet or ingress binding. Its last committed
goal pivot is E-11872, operation `goal-b14d64dda57b46b6bd33833a2b93b776`, with exact
objective `T-1599 (SRC-164): test1`. This history cannot silently become the new
maintenance objective. The active T-1703 / SRC-205 Work and roadmap remain intact.

The independent T-1703 counterexample was a priority disagreement: the router
honored a legal, historically earned budget WAIT while the audit validator
accepted only ingestion or literal active-ticket continuation. The correction
uses the existing `binding_brake` owner and one counter-backed
`goal_valve_wait_is_proven` predicate. An arbitrary WAIT or invented STATE cap
does not suppress pending audits. Resumption preserves active Work before
ordinary audit ingestion; it consumes no audit item.

The new `saipen goal authorize --file <exact operator capsule>` operation uses
`operator_task`, immutable authority-only Source intake, `OperationPlan`, the
writer lock, CAS dependencies, and the existing recovery journal. It appends one
prospective authority-transition DEC and the existing quartet/goal ingress. It
preserves BOARD, task, phase, owner, next action, counters and old receipts.
`goal_authority.prove` retains the original Entry proof and recognizes the new
committed transition through its original pivot, exact objective/event digest,
portable project lineage, ingress, Source digest and original carrier proof.
No path, agent name or maintainer flag grants authority.

Prepared-but-unapplied recovery aborts without granting authority. Partial
application replays exact journaled bytes. Identical committed replay returns
the original operation without a fresh grant or reset. The actual checkpoint
still belongs to `reauthorize_valve`, with counter reconstruction, binding brake
and ownership checks, durable old/new counters and the original authority source.

An additional disposable counterexample found a defect in the first draft:
`set_goal_intent` can retain a previous goal's ingress, and the new transition
initially trusted that field. `ingress-replacement-red.json` records the wrong
ingress being accepted. The final transition derives the ingress from the
original Entry receipt or prospectively from the original event digest/lineage,
binds it in the explicit capsule, and refuses another goal's leftover ingress.
Neither the legacy primitive nor old historical receipts were rewritten.

## Exact implementation files

- `tools/saipen_engine/state.py`
- `tools/saipen_engine/audit_route.py`
- `tools/saipen_engine/router.py`
- `tools/saipen_engine/operations.py`
- `tools/saipen_engine/goal_authority.py`
- `tools/saipen_engine/journal.py`
- `tools/saipen.py`
- `tools/validate.py`
- `tools/test_t1704_goal_checkpoint_priority.py`
- `tools/test_t1704_legacy_goal_authority.py`
- `tests/fixtures/t1703-valve-audit.json`
- `saipen/MAINTENANCE.md`
- `saipen/OPS.md`

These are this correction's paths, not an assertion that all pre-existing Git
changes in those files belong to this Work. No unrelated changes were reverted
or committed. Only the two new test files and captured fixture were added to the
existing Git index. The earlier tested parity delta is `repair.patch` and
`applied.json`; the later transition delta against that tested draft is
`legacy-transition-from-tested-draft.patch` (SHA256
`13d0df275b0b7d24699bba98e4ced0a632aeb5e8379e4182ba5342f7a7fcb71a`).
`legacy-subject.json` retains its baseline and exact resulting source hashes.
The six pre-existing source files are also preserved byte-for-byte under
`legacy-original/`, indexed by `legacy-original.json`, independently of the
temporary baseline's lifetime. Canonical evidence operations additionally wrote
`.saipen/STATE.md`, `.saipen/BOARD.md` and `.saipen/LOG.md` through SAIOPS, including
the normal claim refresh. Their exact target hashes and committed manifests are
listed in `CANONICAL-OPERATIONS.json`; no task identity/phase/counter was changed.

## Validation evidence

- Original unchanged parity oracle: 24 tests, 12 red, exit 1; then 184 focused
  tests, zero red, exit 0 on the initial tested parity draft. Historical evidence
  remains in `REPORT.md` and its referenced records.
- `python -m unittest tools.test_t1704_legacy_goal_authority -q`: initial 13 tests
  all errored because the canonical transition did not exist (exit 1,
  `legacy-red.txt`). The first implementation passed those 13.
- Expanded positive/negative tests exposed draft errors in a source-kind test
  double and journal metadata typing; the original failure outputs are retained.
  The corrected combined set passed 207 tests, exit 0 (`focused-current.txt`).
- Authorization, parity and operation-ID families passed 93 tests, exit 0
  (`authority-focused-green.txt`), then 94 after ingress replacement coverage
  (`authority-ingress-green.txt`).
- The final legacy family passed 28 tests in 61.189 seconds, exit 0
  (`legacy-final-green.txt`). This includes exact phase/counter preservation,
  20-ticket/3-wave continuation, real brakes, model/import/forgery/replay refusal,
  project isolation, old/new journal refusal, Source revocation/corruption,
  concurrent writer/foreign owner refusal, crash recovery, replay idempotence,
  source CAS, original and Source dependency pins, goal replacement and malformed
  authorization refusal. Existing SRC-112 and iteration families remain intact.
- Targeted Ruff and whitespace checks exited 0. No baseline or existing oracle
  was weakened. T-1703's prior 6027/0/0 record is historical, not new evidence
  for this changed source tree.
- Native validation reached CURRENT_PASS with zero problems / nine warnings on
  the earlier final-style subject (`native-current-final.json`, receipt
  `receipt-52bada3c296f`). The later ingress correction changed that subject;
  current-source native validation must be captured again at the final head.
- The first new full-family attempt was explicitly stopped before a summary
  after the ingress replacement counterexample (exit -1); it proves no PASS.
  The final `python tools/core_unit.py evidence T-1704 --fresh --jobs 6` completed
  in 1878.6 seconds: 6079 tests, zero red, zero new red, exit 0, no leaked
  sandboxes. This was an actual fresh run, not reuse of the historical 6027 run.
  Record: `.saipen/evidence/core-unit/474c47ea7d6123b7-20261010T104605Z.json`;
  SHA256 `a01c4f7dd0474398fa89ed852e5fb99544eeec0563844e3cf95c3878ae3773e2`;
  complete copied-tree fingerprint
  `474c47ea7d6123b7ab279fad6ce2c29be85b390215b69d363eb4b25e63872dcb`.
  E-14223 anchors it. The identical complete subject was canonically reused
  for active T-1703 at E-14224; the source did not change.
- Final native command `bin/saipen.cmd validate --json` exited 0 with
  CURRENT_PASS, zero problems / nine warnings at E-14226, receipt
  `receipt-77901f731131`, timestamp `2026-10-10T10:48:23.594590Z`, source
  fingerprint
  `git-delta-v1:b9665d7c5180c218ecd8ce0b4fc9f8bcb5bcd6394fda212084960bf6633214a1`.
  `native-delivery.json` is the complete output. The original post-E-14218
  CURRENT_FAIL remains historical truth for its original subject.
- `status --json` and `explain-next --json` exit 0 and expose bounded authority;
  `iteration --json` exits 0 with OPERATOR_WAIT and `goal_complete: false`.
  An initial diagnostic used the unsupported spelling `explain next` (exit 2,
  retained in `delivery-explain.json`), then used the correct existing command.
  `continue --json` returns RECONCILE_REAUTH_REQUIRED (exit 1) and leaves the
  exact STATE/BOARD/LOG bytes unchanged (`delivery-continue-proof.json`). This
  proves the legacy bounded goal was not upgraded by model execution.

`CHECKS.json` records exact focused commands, exits, outputs and full hashes of
all thirteen implementation paths. The final file hashes equal the frozen
subject. Existing iteration/no-progress and SRC-112 contracts are included in
the completed declared family; no failure/recovery/review cap was disabled.

Live canonical ancillary operations were `saipen work reverify T-1695`,
producing RV-000010, RV-000011 and RV-000012 as the source changed. They preserve
the DONE Work and record `PASS_WITH_CARRIED_DEBT`, never a fabricated overall
PASS. The final native validator separately decides current conformance.

## T-1703 independent REVIEW evidence

The unchanged capture and controls were independently rerun with prefix
`review-recovery-20261010T101737Z`: capture exit 0, controls exit 0. There are 15
registry hosts / 16 installed profile rows, twelve positive and twelve restored
positive controls, and repeated identical red names for three deliberate tool
lies plus one admission lie. Existing oracle hashes are retained by the controls.
The actual doctor exit is 1: Zaicode BROKEN, machine runtime STALE. All live host
boundary probes remain NOT_PROBED; no host/profile was repaired or started.
No completed lifecycle or SHIP/DONE is inferred from these software results.
Memory promotion: NO; the authority-binding lesson is already owned by SRC-112
and the updated maintenance contract.
E-14225 records this independent rerun; E-14226 records the correction evidence.
All four E-14223..E-14226 operations are COMMITTED. The final execution head is
E-14226, still T-1703 / REVIEW, 0 waves / 20 tickets, owner `saipen-cli`. There are
no pending/conflicting operations. T-1704 stays TODO; engineering evidence is not
a fabricated admission/VERIFY/closure cycle.

## Authority, disposition and remaining boundary

No genuine host operator carrier was available to this session. The handoff,
model-supplied SRC-206, host goal metadata and Stop-hook text are not such a
carrier. This implementation therefore does not opt the model or live project
into persistence. A host must transport a genuine exact authorization for the
existing objective; the prospective command is available, but no authentic
capsule for that objective has been supplied. This is an origin/scope boundary,
not a requirement to type another `cc` solely because twenty tickets elapsed.

T-1494 stays DONE. T-1493 remains SUPERSEDED_PENDING:T-1494: the existing
supersession owner refuses Work carrying Source receipts until source migration
is proven (existing canonical recheck E-13999). No exception or fake closure was
introduced. T-1702 and all remaining SRC-205 slices, publication/pilot/account
gates and pending audits remain open and unchanged.

AUDAPACK is a separate P0 NO_GO. Its sealed forensic case is
`../AUDAPACK-T299-forensics/REPORT.md`; original lifecycle files and engineering
evidence were preserved, no safe canonical reconciliation was proven, and no
AUDAPACK admission or closure was performed. Its CURRENT_FAIL is not relabeled
by SAIPEN's separate conformance result.
The final engine was also exercised against AUDAPACK read-only: native core
validation still exits 1 with 19 problems / 79 warnings; recovery preview still
returns HISTORY_LEDGER_CORRUPT, FORENSICALLY_UNRECOVERABLE,
READ_ONLY_DIAGNOSIS_ONLY and no canonical next command. Its four original core
hashes are unchanged. `AUDAPACK-current-engine-checks.json` records both exact
commands and outputs. `AUDAPACK-final-integrity.json` independently confirms
all 8171 sealed case files unchanged (catalog SHA256
`220630f5f8e5c65ecdc107c2b6a78074c4d819d09ed027855db0949d7245659c`).

Next live lifecycle action: NONE until genuine scoped ingress is available.
Task and phase remain T-1703 / REVIEW. This report does not claim mission DONE.
