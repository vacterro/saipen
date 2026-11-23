# T-1494 preparation — not acceptance or a claim

SRC-112 and the expanded BOARD record require persistent authorization to be
machine truth, separate from a new operator reauthorization. Legacy goal intent
and counters alone must default to a bounded run; no earlier model-supplied
receipt may be upgraded merely because it was persisted.

`prepare_controls.py` drives the actual canonical launcher over owned disposable
projects. Both `continue` and `cc` without an original operator carrier reset
20 tickets to zero and replace the hard WAIT with PHASE SHIP. The later SHIP
closure refuses missing verification; that refusal does not undo the unauthorized
budget reset. `cc-before.json`, `continue-before.json` and `preparation-red.txt`
preserve the observation. Four existing fixture/reconciliation controls pass;
the two new authority controls fail. The fixtures are cleaned by their owned
TestCase cleanup. These are partial RED controls, not a complete future oracle.

Relevant current owners, read directly because tools/ is excluded from the graph:

- CLI continue branches in `tools/saipen.py` call `reauthorize_valve` both after
  a reconciliation refusal and after reading counters at cap.
- `operations.reauthorize_valve` checks goal intent and cap, but no original
  operator capability; it resets counters and writes a goal-reauthorized marker.
- `reconcile._tripped_valve_repairs`, state validation/brakes, router, transition
  accounting and stop projection all currently equate a goal cap with hard WAIT.
- Counter reconstruction recognizes goal-pivot and goal-reauthorized markers.

Implementation must use one shared policy over the requested four fields:
continuation_authority, authority_source, authority_until and safety_valve_mode.
Persistent/checkpoint mode needs the immutable original operator authority;
source persistence, raw field assertions, receipt mentions and model assertions
cannot grant it. Bounded/hard-wait mode preserves counters/WAIT without original
operator input. Persistent rollover is a checkpoint/safety review, never a new
reauthorization, and its marker must reconstruct counters correctly. Every
source-dependent mutation must bind the source evidence in the canonical plan.

Before production edits: claim T-1494, load its phase and complete the final
oracle, including genuine operator cc/new-goal positive controls and persistent
20/20 behavior. Re-run the same final oracle on pre-fix and post-fix production;
the present partial RED cannot pay for a changed final oracle. Preserve source
and machine-schema compatibility, and avoid extending this into worker routing
or a resident-runtime redesign.
