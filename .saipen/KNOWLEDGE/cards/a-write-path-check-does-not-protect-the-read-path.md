<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: tools/saipen_engine/operator_task.py, host ingress envelopes, operator carrier provenance
trigger: operator ingress carrier, host_ingress envelope, session binding, replay, wrong-session carrier
status: active
evidence: T-1822, SRC-280, tools/test_t1822_carrier_binding.py, tools/saipen_engine/operator_task.py, .saipen/evidence/T-1822-carrier/red-control.txt
supersedes: none

# A write-path identity check does not protect the read path

`admit_host_ingress()` refused a digest, session or lineage mismatch when it wrote
an envelope, while `witness()` read envelopes with no session filter and matched
on digest alone — so the writer's rule was real and useless. An envelope delivered
by session A was consumed by session B whenever B supplied the same text, and
`authority_for_provenance()` reported `user_explicit: true`: a replayed carrier
earned the operator's authority.

Why:
The check existed in exactly one place, and the place that mattered was the other
one. Reading the writer made the contract look satisfied; only executing the read
showed session A's envelope consumed by session B. The second defect came from the
same instinct: envelopes were named `ing-<digest16>`, a function of the request
TEXT alone, so two sessions delivering identical words shared one filename and the
later write replaced the earlier envelope including its `session_id` and
`message_id` (measured: `m-A` replaced by `m-B`). A durable record whose identity
is an EVENT must not be named after its CONTENT.

Rule: when a record carries an identity field, grep for the reader before
believing the check. The same field must be compared where the value is consumed,
not only where it is written. When the delivering identity cannot be established,
answer with a typed refusal (`HOST_PROVENANCE_UNAVAILABLE`) and leave the owner's
record untouched — never promote it, and never downgrade silently to
`model_supplied`, which would hide that a carrier existed. Name durable records
from the event identity (`message_id` when the host supplies one), and
disambiguate collisions instead of overwriting.

Test shape that catches it: admit the same text from two named sessions, assert
both envelopes survive with both sessions, then assert the wrong session is
refused *and that the owner's envelope is still unconsumed*. The last assertion is
the one that fails when only the return value was fixed.
