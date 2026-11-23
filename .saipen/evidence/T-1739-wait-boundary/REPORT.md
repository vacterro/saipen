# SRC-237 / T-1739: WAIT authority boundary

Partial result: no runtime defect was reproduced for the supplied T-260 state.
Nine regression tests pass; the same oracle rejects a deliberately bad WAIT
projector (five failing assertions/subtests). Both runs bind oracle SHA256
`ccdad540441f4786e64a706937ebb38954ac8b52b557bb8a17d5ea10189cf822`.
Records: `oracle-red.json/.txt` and `oracle-green.json/.txt`.

The native CLI test creates a disposable canonical claim, then assigns the
incident's SCOUT/T-260/WAIT/blocker-none/operator-required/hard-wait input tuple.
It includes two independent TODO candidates and eight BLOCKED records with
allocation history. Its under-budget accounting is normalized to its own
fixture history. Status and continue --dry-run consume the same unchanged
snapshot: claimed_ticket T-260, top_workable_ticket T-283, automation BLOCKED,
next_command null, and the original WAIT returned verbatim. All fixture file
hashes remain unchanged across those two diagnostic calls.

Ownership:
- CORE/COMMANDS and router.binding_brake own session WAIT precedence over Pick.
- STATE.blocker and next_action are separate brakes; blocker none does not
  cancel a WAIT. The goal authority tuple controls budget persistence, not
  permission to accept the power-loss ceiling.
- claimed_ticket/top_workable_ticket are inventory. The latter can name a
  structurally workable TODO while a session brake still prohibits execution.
- actionable and camelCase names in the supplied host report are consumer
  projections, not the canonical automation disposition.
- automation schema 1 owns CONTINUE/COMPLETE/WAIT_USER/WAIT_EXTERNAL/BLOCKED/INVALID.
  Only CONTINUE emits next_command cc. WAIT: blocked is BLOCKED, not a synthetic
  human-decision grant; typed human WAIT categories separately set operator due.
- ZAICODE owns consuming this object without deriving continuation from counts.
  Its actual historical consumer execution was not independently captured here;
  no speculative host/root-cause attribution or runtime change is claimed.

Coverage exercises operator-required WAIT, a blocked claim, independently
eligible Work, dependency-ineligible candidates, absent executable Work,
genuine closure, stale closure, inconsistent authority tuples, and existing
human/read-only gates. No real SAITULS Work or authority was modified.

Full closure is blocked: canonical pinned Ruff 0.16.0 over tools/ and tests/
reports 39 violations in five pre-existing files outside this new oracle.
The new oracle alone lints clean. Full-family evidence was not claimed after
this failed mandatory gate. `lint.json` preserves every finding.
The lint correction requires separate owned Work; SRC-237 remains ACTIVE.

Regression code is preserved as `test_t1739_wait_boundary.py` in this evidence
directory while this partial attempt is parked, for reapplication after the
declared gate is repaired. This is not a completed or shipped regression set.
No protocol rule, runtime behavior, ZAICODE code, ticket closure, durability
decision or historical evidence was changed by this Work.
