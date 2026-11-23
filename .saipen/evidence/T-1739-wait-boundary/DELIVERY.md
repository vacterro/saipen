# SRC-237 / T-1739 authority-boundary delivery

Classification: COMPLETE local evidence. Canonical finish E-16139 closed T-1739
and SRC-237; audit consumption E-16140 preserved the captured source digest.
Git publication is not asserted; T-1644 publication policy remains undecided.

The captured WAIT is correctly non-executable in the current SAIPEN engine.
No runtime correction is justified by the supplied incident. This Work restores
the saved deterministic regression module at `tools/test_t1739_wait_boundary.py`.
Its SHA-256 is `ccdad540441f4786e64a706937ebb38954ac8b52b557bb8a17d5ea10189cf822`,
identical to the originally measured oracle.

## Authority and behavior

- `state.binding_brake` and `router.route_next` evaluate a binding WAIT before
  BOARD selection. `blocker: none` does not discharge `next_action: WAIT: ...`.
- `continuation_authority: operator_required` and `safety_valve_mode: hard_wait`
  describe bounded goal continuation. They do not accept the physical
  power-loss ceiling or independently authorize a gate decision.
- `claimed_ticket` and `top_workable_ticket` are inventory. In the native
  fixture they identify T-260 and T-283 while the same snapshot's canonical
  `automation.disposition` is BLOCKED and `automation.next_command` is null.
- The fixture has two independent TODO candidates and eight blocked records.
  Native status and dry-run continuation consume unchanged bytes; continuation
  returns the exact WAIT. The test hashes every fixture file before and after.
- Without the session brake, T-283 is eligible; adding its unresolved dependency
  removes that eligibility. Counts alone are insufficient.
- `automation._routing_disposition` preserves the existing closed vocabulary.
  Typed human waits produce WAIT_USER and operator_action_due; the incident's
  generic blocked WAIT produces BLOCKED, not an invented question or CONTINUE.
- `automation.closure_gate` requires all current closure conditions. An empty
  executable queue, a stale convergence record, or contradictory authority
  metadata cannot certify completion.

The ZAICODE consumer owns respecting the canonical automation object: execute
only CONTINUE with its declared next_command. The supplied camelCase host
inventory and actionable count cannot override that decision. Historical
ZAICODE execution was not independently captured here, so this result does not
attribute a historical host defect or change host code.

## Evidence

- Current focused run: `resume-green.json` — 9 tests, exit 0.
- Independent REVIEW rerun: `review-green.json` — the same 9 tests pass again;
  the oracle SHA-256 is unchanged. Memory promotion: NO, the existing automation
  truth card already records the reusable rule.
- Existing instrument control: `oracle-red.json` and `oracle-red.txt` — the
  identical oracle rejects a deliberately bad WAIT projector with five failing
  assertions/subtests; `oracle-green.json` binds the same oracle and 9 passes.
- Canonical pinned lint: `python -m ruff check tools/ tests/` — PASS.
- Current full-family record: `../core-unit/532993ba599bc5b3-20261016T042945Z.json`
  — PASS, 6719 tests, 0 red, 0 new red, no leaked sandbox.
- Canonical core conformance: CURRENT_PASS, `receipt-7e62ea3684a2`, 0 problems,
  9 advisory warnings. Both missing test files were registered in the Git index.
- T-1695's existing focused contract was explicitly remeasured without changing
  its oracle or scope: RV-000073, 38 passing tests, 686 dependencies, CURRENT_PASS.
  Strict-only RV-000072 could not refresh the older ENVIRONMENT_CHANGED focused
  observation. DONE and historical closure stayed intact throughout.
- Prior dependency T-1741 completed canonically at E-15047; T-1739 was
  journaledly unblocked at E-16120 and freshly claimed at E-16121.

## Contract coverage

| Clause | Witness |
| --- | --- |
| R001 | Current state.binding_brake, router.route_next, automation._routing_disposition, automation.closure_gate; authority analysis above |
| R002 | Native status/continue fixture and complete before/after file hashes |
| R003 | WAIT dominance and independent/dependency-ineligible candidate tests |
| R004 | Correct current protocol behavior; test-only change; bounded consumer responsibility above |
| R005 | test_operator_required_wait_dominates_two_candidates_and_eight_blocked |
| R006 | test_blocked_claimed_ticket_cannot_grant_execution |
| R007 | test_independent_candidate_is_eligible_only_after_session_brake_absent |
| R008 | test_no_executable_work_is_not_completion |
| R009 | test_genuine_complete_requires_all_current_closure_conditions |
| R010 | test_stale_projection_cannot_certify_current_completion |
| R011 | test_contradictory_authority_tuple_fails_closed |
| R012 | test_safety_gates_and_existing_schema_remain_intact |
| R013 | Native existing-schema compatibility, canonical lint, 6719-test full-family PASS, core CURRENT_PASS |
| R014 | Disposable fixtures only; no actual SAITULS gate, authority, or lifecycle mutation |
| R015 | No runtime/rule/ZAICODE change or speculative finding ticket |
| R016 | This verified boundary result and completed required full-family/core gates |

No real SAITULS source, durability decision, T-260 WAIT, or ZAICODE code is
changed by this Work. Source closure and audit consumption remain their
canonical operations.
