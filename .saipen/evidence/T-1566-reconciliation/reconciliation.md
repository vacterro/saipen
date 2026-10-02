# Stabilization graph reconciliation — SRC-144

## Root cause and canonical route

SRC-143 contains target-free continuation of the active stabilization goal, not
an independent implementation target. `start_work` only checked exact request
deduplication before calling `user_request`; every new body was projected as
`user_explicit` Work and parked the active ticket. E-10844/E-10845 therefore
created a false preemption: unfinished T-1563 admission bytes contaminated the
full family needed for T-1565 VERIFY while T-1563 waited for T-1565 completion.

The existing OPS HANDBACK transaction is the recovery route, not retirement,
supersession, completion or baseline growth. E-10855/E-10856 handed the newly
captured corrective request T-1566 back to T-1565. E-10857/E-10858 handed
T-1565 back to T-1563 at its saved BUILD/SCOUT tuple. Both operations were
journaled; neither ticket closed. E-10859 records the corrected interpretation.
SRC-143 and SRC-144 gained canonical membership in T-1563 while their original
primary linkage remains historical attribution. Original source bodies and
all earlier LOG events remain untouched.

T-1565 remains useful bounded foreign-tail repair Work, queued for coherent-tree
verification with its explicit verify contract updated by E-10860. Its repair
bytes were not reverted. T-1566 remains corrective verification Work, not a
new implementation owner. No reverse dependency from T-1563 to either queued
verification ticket remains.

## Regression and controls

The same continuation oracle on the original implementation produced six
behavioral failures: five target-free START forms created T-2 and parked T-1;
`user-request` also forked a second ticket. Concrete new-target controls and
no-active-goal controls passed. The repaired bounded full-message grammar
preserves current Work/phase/budget for those forms, including exact SRC-143,
and rejects unknown or concrete remainders as independent requests. Semantic
classification outside this narrow convenience grammar remains agent-owned.

The foreign-tail public CLI oracle now imports the repair API only when needed.
Its identical bytes ran against the isolated pre-fix subject, collected and
executed: checkpoint returned HISTORY_LEDGER_CORRUPT, recover reported
FORENSICALLY_UNRECOVERABLE, and canonical_next_command was null. It failed on
that measured behavior, not missing API collection. See the hash-bound JSON
and behavioral RED log alongside this report. Post-fix the same oracle names
quarantine-log-tail, checks preserved original bytes, SHA256 and prefix,
requires the canonical repair event, and runs validate successfully.

## Admission honesty and coherent tests

No production separated host authority exists. T-1563 containment is unchanged:
no bootstrap key reader, MAC/provenance signer, adapter signer or local broker
was restored. Real ordinary-process adversarial controls still run and refuse.

Generation/delivery/response/style tests now explicitly isolate downstream
logic with test-only dependency doubles. They are not evidence of host authority:
no production writer/provider/key/environment bypass was added. Real CLI/hook
positive admission tests remain present but explicitly skipped with
CAPABILITY_UNAVAILABLE and SRC-140:R009 BLOCKED. Ten positive integration
obligations are unavailable, not passed. The exact vulnerable carrier still
proves ADMITTED only on the frozen vulnerable subject and refusal on production.

Focused admission/Claude/security run: 118 tests, zero failures, ten explicit
CAPABILITY_UNAVAILABLE skips. Focused continuation/quarantine/security/guard
run: 60 tests, zero failures. Separate classifier/line-ending controls: six
tests, zero failures after correcting fixtures that assumed an LF checkout and
a pre-layering CLI symbol. Full-family results will be recorded separately;
these focused results cannot close T-1565 or T-1563.

The 73 prior new reds are never added to the baseline and are never attributed
to the foreign-tail repair. A later new_red=0 over the coherent suite does NOT
prove positive admission or discharge blocked source acceptance. T-1563,
T-1562 and T-1558 cannot be reported complete while that authority is missing.

## Preserved foreign-tail invariants

The raw appender remains zero-write. Cut authority is checkpointed last_event;
any suffix event above it refuses. The kept prefix must satisfy the complete
immutable ledger contract. Original LOG bytes survive as evidence, a canonical
repair event records the operation, recover exposes its exact command, and
both repair evidence roots remain durable and byte-bound. Existing negative
controls remain enabled; no proof predicate was weakened.
