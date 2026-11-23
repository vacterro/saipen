<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: convention
scope: STATE.next_action, execution_intent converge, router.gate_route, saipen status --json automation block, host drivers and supervisors
trigger: deciding whether a persisted STATE action authorizes a host or agent to execute it
status: active
evidence: T-2081, .saipen/evidence/T-2081/FIXED-POINT-AUDIT.md, .saipen/evidence/T-2081/fixed-point.json, tools/saipen.py:1958, tools/saipen_engine/router.py:1241, tools/saipen_engine/automation.py:210
supersedes: none

# STATE.next_action is recorded intent; only the gated route is authority

A persisted `STATE.next_action` is written when a previous step finishes; it is not proof that the route is executable now, because every machine surface publishes the answer only after `router.gate_route` has had the chance to rewrite it into a refusal.

Why:
Measured on T-2081: `STATE.next_action: "saipen crew"` under `execution_intent: converge` / `converge_target: crew` produced a raw route of `crew-converge` / `saipen crew`, which `router.gate_route` rewrote to `CONFORMANCE_UNHEALTHY`, `automation.disposition BLOCKED`, `next_command null`. A host that dispatched the persisted string would run a command every SAIPEN surface had already refused, and a retry that leaves the state identity unchanged is a stall rather than progress.

How to apply:
Read the `automation` block (`disposition`, `next_command`) from `saipen status --json`, or the classification from the continuation assessment. Treat `STATE.next_action` and `converge_target` as history of intent, never as permission.
