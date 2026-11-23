# T-1729 / SRC-228 — operator-decision provenance and WAIT lifecycle

Classification: **PARTIAL**. The engine correction and focused regressions are
implemented. The declared family is still in flight in another process, and
no genuine independently witnessed operator decision has been obtained.
SRC-228:R019 remains BLOCKED. Nothing here claims DONE or publication.

## Root cause and flow

The original `_state_blocker_repairs` treated any nonempty `resolve_blocker`
argument as `operator_authorized`, although canonical recording proves only
operation provenance. It cleared `STATE.blocker` without invalidating a legal
`WAIT:` in `next_action`. `_state_next_action_repairs` immediately ignored
legal WAIT strings. `binding_brake`, shared by the router and admission,
therefore continued to bind the independently stored stale WAIT.

The corrected path is:

1. Original external operator input is compared by `operator_task.witness`.
2. `operations.authority_capture` preserves the exact capsule as an
   authority-only Source. Capture itself grants nothing and creates no Work.
3. `goal_authority.source_proof` checks the immutable original witness, exact
   body integrity, status and distribution/revocation state. A stronger
   environment on a later retry cannot promote a model-supplied Source.
4. `gate_decision.resolve` checks decision content, project lineage, exact
   gate version and UTC expiry. Its gate id hashes phase, task, last_event,
   blocker and next_action together with lineage; that digest proves scope,
   never human origin.
5. The existing `_state_only_plan` and `apply_plan` commit LOG and STATE, plus
   preserved original STATE bytes, through the existing reconciliation
   journal. Source, identity, BOARD and history reads remain CAS dependencies.
6. The shared router projects the replacement next action, or validates the
   executable replacement present in the witnessed capsule. Only explicitly
   named fields are resolved. BOARD and unrelated stop owners are preserved.
7. Journal recovery aborts a zero-write prepare or rolls partial writes
   forward. Changed authority dependencies cause conflict, rather than a new
   grant. `binding_brake` and router admission consume the resulting STATE.
8. Restart/reconcile preserves the discharged projection. Repeated acceptance
   verifies its original Source and committed event, then writes nothing; it
   never discharges a later gate. Lifecycle repairs retain priority, including
   CURRENT_DONE_JOURNAL_GAP; a gate approval cannot conceal them.

There is no new approval override, signer, authority store or deployment path.
The gate owner extends the existing Source and journal mechanisms.

## Files changed in this correction

- `tools/saipen_engine/gate_decision.py`: closed scoped-capsule contract and
  journaled state transition.
- `tools/saipen_engine/operations.py`: accept gate capsules through the existing
  authority-only capture surface.
- `tools/saipen_engine/reconcile.py`: remove text-derived authority; preserve
  lifecycle-repair priority and route scoped decisions to their owner.
- `tools/saipen.py`: recovery usage names authority Source receipts.
- `tools/saipen_engine/admission.py`, `fleet.py`: receipt-based remediation.
- `saipen/OPS.md`, `COMMANDS.md`: the provenance and lifecycle contract.
- `tools/test_t1729_operator_gate.py`, `test_t1729_gate_decision_lifecycle.py`:
  disposable provenance, history, crash, restart, scope and replay matrices.
- Existing recovery, next-action, oversized-event, refusal-route and command
  reachability tests now provide explicit harness authority when appropriate.

Unrelated inherited changes remain. The three pre-change implementation
files are preserved under `before/`. The separately produced fam4 log was
preserved as `parallel-fam4.txt`; other parallel artifacts are not attributed
to this implementation.

## Verification evidence

- `focused-checks.json`: 37 focused tests PASS, including both new matrices,
  the lifecycle-gap masking regression and admission's exact remediation.
- Same file: 21 whole-source contract tests PASS; Ruff 0.16.0 over `tools/`
  and `tests/` PASS.
- Executed native regression pair: E-16153 FAIL and E-16154 PASS, unchanged
  verifier `0f0e5d9c29049d2c4b4397781e90e9208b454fa08999e5ec0024cd473dd9e0c7`.
  All three tests fail on the saved pre-change implementation, and all three
  pass after. The failures demonstrate text-derived approval, the stale WAIT,
  and unsupported native capture; they are assertion failures, not imports.
- Immutable pair receipt:
  `.saipen/evidence/regression/regression-execution-3d494d7f7c0b4320919fe69bdd194448.json`.
- The crash matrix exercises PREPARED, LOG, STATE, preserved-evidence and
  VERIFIED stages. It also rejects changed authority during recovery and
  source/identity races before APPLY.
- Historical fixtures contain E-3003, E-3009, E-3010 and E-3011 in a valid
  consecutive ledger, and exercise the real binding brake and router. A
  separate test commits a real ticket_move without a witness and proves that
  it grants no gate authority.
- A separately observed parallel pytest run reports 145 PASS. It is additional
  evidence, not the required declared-family receipt. An earlier owned family
  run was cancelled after a parallel log inside `tools/` invalidated its
  source snapshot; it supplies no PASS evidence.

## Runtime and incident status

`runtime.json` preserves the native launcher and preview output. PATH resolves
to this checkout's `tools/saipen.py` through Python 3.11; its fresh native
preview loads the new gate owner. Source and executing engine share the same
origin, version 8.1.0. No consumer installation was deployed or published.

Read-only SAITULS observation reports DONE, task none, next_action
`saipen continue`, blocker none, E-3243, head `5f0dc0c`. Its historical WAIT is
no longer active. This session did not establish the origin of that change,
did not alter SAITULS, and did not start or close T-285/T-286. E-3009 remains
canonical-recorded but operator-authority-unverified here; no historical
evidence was upgraded, no unrelated stop was cleared, and no held goal Work
was dispatched.

## Unmet genuine acceptance and remaining action

No operator task digest or task-file carrier is present in this session.
Fixture carriers are explicitly TEST HARNESS witnesses, not real operator
acceptance. In particular, the separately created
`tools/_t1729_acceptance.py` computes a digest from text it generated itself
and puts that value in `SAIPEN_TASK_SHA256`. Its process/restart results may
demonstrate the harness path; its "real carrier" label cannot establish
independent human origin and cannot discharge SRC-228:R019.

A real operator must supply an independently witnessed, original decision
for a new disposable gate: exact project lineage and gate version,
ACCEPT_LIMITATION content, selected fields and future UTC expiry. Capture
those original bytes through the existing trusted carrier, apply the matching
Source via `recover resolve-blocker SRC-N` or the next_action-only recovery
verb, and demonstrate native resume plus restart/reconcile stability. Preserve
the exact receipt and observations. This mission, `cc al`, and any digest
generated by the agent are not that approval. No SAITULS mutation is requested.

## REVIEW verdict (this session)

REVIEW re-ran the ticket's own verifiers instead of reading VERIFY's claim and
agreed with it (see `review-independent.txt`): the gate-decision matrix 15/15,
the operator-gate family 20/20, recovery reachability 84/84, the declared
triple 3/3, hermetic env 3/3. No oracle moved to make the change pass: the
pinned families still assert exact canonical routes
(`saipen recover resolve-blocker`, `saipen recover resolve-next-action`,
`verify -> PASS [target: T-] conf: high`) and pass. VERIFY-ORACLE-01 is answered
by the freshly anchored pair `regression-execution-3325af29`: before FAIL, after
PASS, identical verifier digest, so the pre-fix red belongs to the verifier that
now passes. Memory-promotion check answered NO: the refusal-ordering rule is
already pinned by `test_recovery_reachability.test_the_verb_does_not_own_phase_blocked`
and the T-1572 matrix_J, so a card would only duplicate encoded tests. Verdict
recorded as `DEC: SHIP` (event E-16165); no P0/P1 finding, no follow-up ticket.

One incidental finding, P3 and outside this ticket's surface: the earlier
`VERIFY -> REVIEW` attempt was refused twice for evidence shape reasons
(`conf: high` verdict token, then `STALE_REGRESSION_EVIDENCE` after scratch
files under `tools/` moved the tree fingerprint). Both refusals are the
machinery working as designed; the second one names a real trap -- an untracked
scratch file in the source tree silently invalidates a regression binding. It is
not ticketed here because it is a workflow consequence, not a defect.

The full declared family and final current-tree conformance remain due before
claiming the engineering gates complete. Genuine acceptance remains due
before DONE even if every automated gate is green.
