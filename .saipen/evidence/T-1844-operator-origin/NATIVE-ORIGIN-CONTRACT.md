# T-1844 native operator-event integration

Implementation notes for T-1819 / SRC-278. This is a reviewable local interface,
not evidence that a Freebuff callback or UI has been integrated. No installed
Freebuff artifact was changed. The real host A/O/P and T-1479 gates remain due.

## Trust and delivery

The existing separated broker owns the ephemeral HMAC key, exact event records,
worker bindings and consumption. No key file, new authority daemon, environment
flag or caller-declared authentication is introduced. Production consumers call
the authenticated default endpoint; the new client methods accept no diagnostic
runtime override.

`host_authority_client.issue_operator_origin(...)` is callable only from a native
invocation that passes the broker's existing OS/shipped-hook identity verifier.
Supply the actual project, host session, original human bytes, native event ID
and intended action. The action vocabulary is `start`, `continue`, `goal`,
`authorize-goal`, `append`, `handoff`, `report`, `resolve-gate`, `retire`,
`supersede`. Each privileged caller requires its own matching action; an
authenticated report cannot substitute for those decisions. The broker binds content digest,
root, project lineage, session, task/goal scope, action, issuer generation,
native host PID/birth, nonce and expiry. Event-ID redelivery is idempotent;
changed content, scope or host birth refuses.

`register_operator_worker(proof, worker_pid)` must be invoked by the genuine
native spawner using the process it actually created. The broker observes its
ancestry and birth. Never register the shared host/orchestrator process, use a
model-provided PID, or substitute a session environment variable for this step.
Nested CLI processes inherit authority only through the registered OS ancestor.
An unrelated worker cannot borrow a readable proof. Revoke the old event before
assigning its live worker to a different event. An authenticated native spawner
can register a replacement worker for an already committed goal after delivery
expiry; this does not restore a fresh delivery capability.

Transport the returned proof as `operator_origin` on the existing ingress
envelope together with exact `request_text`, `request_digest`, `session_id` and
`message_id`. `admit_host_ingress()` preserves it but does not authenticate it.
The session carrier selects a matching envelope; signature, live owner, scope
and independently observed worker determine authority. A task file/digest can
still transport and compare bytes. It grants no privilege by itself, and a
matching file does not bypass checking an available native-event proof.

`revoke_operator_origin(proof)` requires the native writer identity. Revocation
or broker loss rejects further privileged use. Historical `model_supplied`
records are never promoted by a later carrier or proof.

## First effect and continuation

Ordinary start captures the exact Source first. Broker verification binds one
event to one canonical Source; a copied second Source grants nothing. Native
envelope retirement follows successful Source binding, not a preview. Expired,
wrong-task, wrong-goal or spent-budget Source references cannot mint privileges.
Capture and local model work remain available without operator origin.

Goal entry and existing-goal authorization reserve one stable operation named
from the native nonce before APPLY. The broker retains the exact intended goal,
grant fields, semantic hash and operation ID. Goal verification requires the
original COMMITTED journal and unchanged goal epoch. A model-written journal
without the live reservation proves nothing. A valid accepted goal can continue
across task churn and delivery expiry; it cannot authorize another goal, a new
delivery or a reset from an expired proof. Refused APPLY can retry the same
reserved goal-entry operation without allocating another effect.

## Actual coverage and open work

`test_t1844_origin_broker.py` exercises the real broker and consumer with
explicitly simulated native identity/process facts. It covers issuer refusal,
registered descendants, wrong worker/session/project/content/action, PID reuse,
malformed proofs/actions, expiry, Source replay, revocation, issuer loss,
historical model truth, file transport, entry/Source/BOARD projection, committed
goal continuation, goal journal tampering and a refused-APPLY retry. The existing
real-process broker IdentityTests independently exercise native client refusal.
Neither category proves Freebuff UI integration.

Legacy goal/continuation/ingress fixtures now use an explicitly isolated broker
while preserving positive, negative, crash, cold-process and validator coverage.
Their prior selected results remain evidence only for the generations they ran.
The original unchanged eight-test carrier oracle and the four event-aware
authority-preview controls now have native executed FAIL/PASS records.
CURRENT.md names those records and the live complete-family observation handle.
The final whole-family verdict, REVIEW and local closure remain due.

Freebuff still needs a genuine trusted human-event callback and trusted tool
spawner bridge compatible with the broker's registered native identity policy.
The installed-source locations already inspected for the parent are recorded in
the earlier BUILD.md. A generic CLI wrapper, `messageThread` model input, an
environment marker or an admitted-session token cannot stand in for that bridge.
