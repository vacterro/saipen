# T-1750 bounded readonly preparation during T-1801 family

No T-1750 product edit or closure is claimed. Original evidence is
`.saipen/evidence/T-1746-crew-terminal/REPORT.md` sections 7/9.

Current `tools/saipen_engine/release.py` confirms both reported branches:

- `_apply_no_publish_locked` starts its journal before `_no_publish_body`;
  its ReleaseRefusal branch returns NO_PUBLISH without settlement. The body
  raises on core validation before `_apply_finish_targets`. Existing
  `_recover_no_publish` aborts a zero-applied-target operation separately.
  Automatically settle only refusal proven to have landed no closure target;
  partial application still requires recovery. Preserve crash-before-body and
  unresolved-sibling controls and account for live target bytes, not just flags.
- `_gate_command` accepts any root/tools/validate.py because it exists. The
  runtime's canonical validator is beside this engine. An unrelated managed
  project script must not gain authority from its filename; invoke the runtime
  validator with --project-root. Direct self-home validation stays available
  when root actually is the running home.

`tools/test_t1746_crew_terminal_outcome.py` encodes both old behaviors:
ManagedProjectGate treats a disposable local no-op validator as canonical;
RecoveryAndReceipts requires manual recovery after a refused validation.
Update those assertions in the eventual owned scope while retaining useful
controls. Its `_DownstreamShape` has real release plan/execute/journal/recovery
plumbing with crew readiness/parity supplied. Add an independent frozen oracle
and run original/fixed release.py against the same fixture/oracle bytes.

Graph project/coverage transport returned Transport closed; exact source and
fixtures were read directly. No exhaustive graph claim. Stay readonly during
T-1801 session 14999; approved T-1765 is the next selected repair afterward.

Later readonly discovery during T-1765 family: an earlier unapplied proposal
exists at `.saipen/evidence/T-1750-no-publish-gate/apply_t1750.py`, with a draft
test beneath draft/. Its validator-authority and old-test adjustments are useful
review inputs. Do not apply it blindly: it aborts only `_run_gate` rejection
inside `_no_publish_body`. Current `_apply_finish_targets` explicitly calls
`_release_receipt_target` before applying any closure target, and that helper
may raise ReleaseRefusal even after a green gate. Thus a healthy journal with
zero landed targets can still be stranded by that proposal. The acceptance's
general pre-target refusal needs a control for this later preparation refusal,
and a partial-target refusal control must still require recovery. Prefer the
existing caught-body refusal/target classifier and journal owner over another
state or special recovery command. No candidate was applied here.
