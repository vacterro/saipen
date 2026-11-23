# T-1494 read-only design preparation

This is preparation during T-1507's frozen full-family run, not a claim or an
implemented fix. SRC-112:R002-R005 are the acceptance authority. The two actual
canonical-launcher bounded controls in prepare_controls.py remain RED: agent
continue and agent cc reset an exhausted legacy budget without an original
operator carrier. Their rejection later in SHIP does not undo that reset.

Reuse operator_task.authority_for_provenance and authority_for_receipt for
operator capabilities. A receipt body's fidelity is not a grant; model_supplied
and transport_obligation must stay bounded. Never relabel a legacy receipt or
this project's old goal as operator_persistent because an agent recalls /goal.

One policy should own the four typed fields (continuation_authority,
authority_source, authority_until, safety_valve_mode) and the two compatible
profiles. Missing legacy fields mean bounded hard_wait. Partial, malformed or
contradictory fields fail closed. Persistent authority must resolve an original
integrity-checked authorized receipt or a journaled grant tied to that receipt;
an arbitrary GOAL event or free-text mention supplies no grant.

The policy must be consumed consistently by goal entry, ordinary continuation,
reauthorize_valve, finish/transition counter checkpoints, reconciliation,
routing and validation. An agent invocation never renews bounded authority.
Actual original operator cc may renew it; explicit witnessed /goal may create
the persistent profile. A persistent ceiling performs a journaled checkpoint
and safety review under the original authority, not a new operator grant.
Counter reconstruction must understand that checkpoint marker, otherwise the
next recover call will restore the exhausted count and deadlock continuation.

Bind authority bytes and metadata as read dependencies in any mutation plan.
The same authority predicate must be rechecked under CAS/locking, so a changed
source between planning and application cannot grant continuation. Neither
mode can waive human, integrity, execution, publication or safety boundaries.

The final fixed oracle needs positives for witnessed persistent ceilings and
real original cc, negatives for both agent aliases, legacy/default bounded
state, model-supplied exact receipts, forged/deleted/changed authority, partial
STATE fields and read-dependency races. Hold oracle/configuration fixed and
rerun RED before implementing the production policy; the preparation pair is
not a substitute for this acceptance matrix.
